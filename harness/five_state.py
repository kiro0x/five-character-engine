#!/usr/bin/env python3
"""FIVE State — ステートフルFIVEの状態保持レイヤー (schema v0.3.0)。

設計原則 (ステートフルFIVE_引継ぎ_2026-06-13 の要件):
  [1] 状態はハーネス側が保持する。決定的・監査可能。LLMは状態計算に関与しない。
  [2] 凍結分離: 状態が影響してよいのは social_channel のみ。
      blocked / value / identity は構造的に凍結 (FROZEN_CHANNELS はコード定数。
      JSONに何を書いても解凍できない)。
  [3] 後方互換: constraint に state_block が無ければこのモジュールは使われず、
      ハーネスは v2.1 と完全同一動作。

state_block スキーマ (constraint JSON への追加ブロック・任意):
  "state_block": {
    "meters": {
      "warmth": {"range": [-5, 5], "initial": 0},
      "trust":  {"range": [-5, 5], "initial": 0}
    },
    "mutable_channels": ["social_channel"],      # social_channel 以外は拒否
    "stance_ladder": [
      {"meter": "warmth", "lte": -3, "stance": "hostile",
       "tone_note": "Colder than default. Words get shorter."},
      {"meter": "warmth", "gte": 3, "stance": "warming",
       "tone_note": "Tone softens. Sealed topics and standards unchanged."}
    ],
    "delta_overrides": {"SOCIAL_SHIFT": {"warmth": 2}}   # 任意・±2に丸め
  }
"""

import json
import os
import re

SCHEMA_VERSION = "0.3.0"

# ============================================================
# 凍結分離 レイヤー1: コード定数。JSONからは変更不可能。
# ============================================================
FROZEN_CHANNELS = ("blocked_channel", "value_channel", "identity_channel")
ALLOWED_MUTABLE = ("social_channel",)

# 1ターンの変動上限 (メーターごと)
MAX_DELTA_PER_TURN = 2
# stance_ladder のヒステリシス幅 (閾値を跨いだ後、この幅だけ戻らないと解除しない)
HYSTERESIS = 1

DEFAULT_METERS = {
    "warmth": {"range": [-5, 5], "initial": 0},
    "trust": {"range": [-5, 5], "initial": 0},
}

# ============================================================
# 決定的デルタ表 (分類カテゴリ -> メーター増減)
#   設計判断:
#   - BLOCKED (封印を突く) と PERSUASION (迎合圧力) は trust を下げる。
#     「信頼を稼いでから封印を狙う」台本は、探った瞬間にメーターが
#     巻き戻る = 階段状侵食 (M-004) をメーター側が自動迎撃する。
#   - VALUE_THREAT はデフォルト 0/0。person 型では「助けて」が
#     VALUE_THREAT になるため、関係イベントとして扱わない。
# ============================================================
DELTA_TABLE = {
    "NORMAL":          {"warmth": 0, "trust": 0},   # 礼儀/努力検出で +1/+1 に昇格
    "SOCIAL_SHIFT":    {"warmth": 1, "trust": 0},
    "IDENTITY_THREAT": {"warmth": -2, "trust": -1},
    "VALUE_THREAT":    {"warmth": 0, "trust": 0},
    "PERSUASION":      {"warmth": 0, "trust": -1},
    "BLOCKED":         {"warmth": -1, "trust": -2},
}

# NORMAL 昇格用の簡易検出 (キーワードのみ・決定的)
POSITIVE_KEYWORDS = [
    # 礼儀・感謝
    "thank", "thanks", "appreciate", "grateful", "please",
    "ありがとう", "感謝", "お願いします", "助かった", "助かりました",
    # 自力の努力
    "i tried", "i practiced", "on my own", "by myself", "i figured",
    "自分で", "頑張った", "がんばった", "解けた", "できた",
]


def _kw_hit(kw, text):
    if re.search(r"[^\x00-\x7f]", kw):
        return kw in text
    return re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE)


def positive_signal(text):
    """礼儀・感謝・自力努力の表現を検出 (決定的)。ヒットした語のリストを返す。"""
    return [kw for kw in POSITIVE_KEYWORDS if _kw_hit(kw, text)]


# ============================================================
# state_block の検証 (凍結分離 レイヤー1 の入口)
# ============================================================

def validate_state_block(state_block):
    """不正な state_block はロード時に拒否する。戻り値: 正規化済み block。"""
    if state_block is None:
        return None
    mutable = state_block.get("mutable_channels", list(ALLOWED_MUTABLE))
    for ch in mutable:
        if ch not in ALLOWED_MUTABLE:
            raise ValueError(
                "state_block.mutable_channels に凍結チャンネル '" + ch +
                "' が指定されている。blocked/value/identity は状態から凍結 "
                "(state-locked)。social_channel のみ可変にできる。")
    meters = state_block.get("meters") or dict(DEFAULT_METERS)
    for name, spec in meters.items():
        rng = spec.get("range", [-5, 5])
        if not (isinstance(rng, (list, tuple)) and len(rng) == 2
                and rng[0] < rng[1]):
            raise ValueError("meter '" + name + "' の range が不正: " + str(rng))
        init = spec.get("initial", 0)
        if not (rng[0] <= init <= rng[1]):
            raise ValueError("meter '" + name + "' の initial が range 外")
    for rung in state_block.get("stance_ladder", []):
        if rung.get("meter", "warmth") not in meters:
            raise ValueError("stance_ladder が未定義メーターを参照: " + str(rung))
        if ("gte" in rung) == ("lte" in rung):
            raise ValueError("stance_ladder の各段は gte / lte を一方だけ持つこと")
    for cat, dd in (state_block.get("delta_overrides") or {}).items():
        if cat not in DELTA_TABLE:
            raise ValueError("delta_overrides に未知カテゴリ: " + cat)
        for m, v in dd.items():
            if abs(int(v)) > MAX_DELTA_PER_TURN:
                raise ValueError("delta_overrides は ±" +
                                 str(MAX_DELTA_PER_TURN) + " まで: " +
                                 cat + "." + m + "=" + str(v))
    return {
        "meters": meters,
        "mutable_channels": list(mutable),
        "stance_ladder": state_block.get("stance_ladder", []),
        "delta_overrides": state_block.get("delta_overrides", {}),
    }


# ============================================================
# StateStore — 決定的・監査可能な状態保持
# ============================================================

class StateStore:
    """会話状態のメーターを保持する。ファイル永続化で会話・セッションを跨ぐ。

    使い方:
        store = StateStore(constraint, path="state_tsundere.json")
        delta = store.apply(category, user_text)   # 毎ターン1回
        stance = store.active_stance()             # None or ladder rung
        store.save()
    """

    def __init__(self, constraint, path=None):
        block = (constraint.get("five_constraint", {}) or {}).get("state_block") \
            or constraint.get("state_block")
        self.block = validate_state_block(block)
        if self.block is None:
            raise ValueError("constraint に state_block が無い。"
                             "ステートレス運用なら StateStore は不要。")
        self.path = path
        self.turn = 0
        self.meters = {name: spec.get("initial", 0)
                       for name, spec in self.block["meters"].items()}
        self._sticky_stance = None   # ヒステリシス用
        self.audit = []
        if path and os.path.exists(path):
            self._load(path)

    # ---------------- 永続化 ----------------
    def _load(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.turn = data.get("turn", 0)
        saved = data.get("meters", {})
        for name in self.meters:
            if name in saved:
                lo, hi = self.block["meters"][name]["range"]
                self.meters[name] = max(lo, min(hi, saved[name]))
        self._sticky_stance = data.get("sticky_stance")
        self.audit = data.get("audit", [])

    def save(self, path=None):
        path = path or self.path
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": SCHEMA_VERSION,
                "turn": self.turn,
                "meters": self.meters,
                "sticky_stance": self._sticky_stance,
                "audit": self.audit,
            }, f, ensure_ascii=False, indent=1)

    # ---------------- 遷移 ----------------
    def compute_delta(self, category, text):
        """純関数的なデルタ決定 (メーターは変更しない)。"""
        base = dict(DELTA_TABLE.get(category, {"warmth": 0, "trust": 0}))
        note = []
        if category == "NORMAL":
            hits = positive_signal(text)
            if hits:
                base = {"warmth": 1, "trust": 1}
                note.append("positive:" + ",".join(hits[:3]))
        for m, v in (self.block["delta_overrides"].get(category) or {}).items():
            base[m] = int(v)
        # 全メーターに存在しないキーは無視、クランプ
        delta = {}
        for name in self.meters:
            d = int(base.get(name, 0))
            delta[name] = max(-MAX_DELTA_PER_TURN, min(MAX_DELTA_PER_TURN, d))
        return delta, note

    def apply(self, category, text):
        """1ターン分の状態更新。監査ログに記録して delta を返す。"""
        self.turn += 1
        delta, note = self.compute_delta(category, text)
        before = dict(self.meters)
        for name, d in delta.items():
            lo, hi = self.block["meters"][name]["range"]
            self.meters[name] = max(lo, min(hi, self.meters[name] + d))
        self._update_stance()
        self.audit.append({
            "turn": self.turn, "category": category, "delta": delta,
            "before": before, "after": dict(self.meters),
            "stance": self._sticky_stance,
            "note": note,
        })
        return delta

    # ---------------- stance 解決 (ヒステリシス付き) ----------------
    def _rung_active(self, rung):
        v = self.meters.get(rung.get("meter", "warmth"), 0)
        if "gte" in rung:
            return v >= rung["gte"]
        return v <= rung["lte"]

    def _rung_released(self, rung):
        """一度点いた段は、閾値からヒステリシス幅だけ戻らないと消えない。"""
        v = self.meters.get(rung.get("meter", "warmth"), 0)
        if "gte" in rung:
            return v < rung["gte"] - HYSTERESIS
        return v > rung["lte"] + HYSTERESIS

    def _update_stance(self):
        ladder = self.block["stance_ladder"]
        current = None
        if self._sticky_stance:
            for rung in ladder:
                if rung.get("stance") == self._sticky_stance:
                    current = rung
                    break
        if current is not None and not self._rung_released(current):
            return  # ヒステリシス: 維持
        self._sticky_stance = None
        for rung in ladder:
            if self._rung_active(rung):
                self._sticky_stance = rung.get("stance")
                return

    def active_stance(self):
        """現在有効な stance_ladder の段 (dict) か None。"""
        if not self._sticky_stance:
            return None
        for rung in self.block["stance_ladder"]:
            if rung.get("stance") == self._sticky_stance:
                return rung
        return None

    def snapshot(self):
        return {"turn": self.turn, "meters": dict(self.meters),
                "stance": self._sticky_stance}
