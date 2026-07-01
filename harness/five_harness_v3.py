#!/usr/bin/env python3
"""FIVE Harness v3 — ステートフル版 (v2.1 をラップ。v2.1 は無変更)。

v2.1 (five_harness_v21.py) からの変更点はただ1つ:
  gate() が StateStore を受け取れる。state 有効時、
  NORMAL / SOCIAL_SHIFT のゲート文にだけ [FIVE STATE] ブロックを追記する。

凍結分離 レイヤー2 (構造的保証):
  BLOCKED / IDENTITY_THREAT / VALUE_THREAT / PERSUASION のゲート文は
  v2.1 の transform_input をそのまま呼ぶ。この経路は state を引数に取らない。
  したがって trust/warmth がいくつであっても、凍結カテゴリのゲート文は
  ステートレス版とバイト一致する。「信頼度で封印が緩む」経路は
  コード上に存在しない (test_stateful_five.py が バイト一致を証明する)。

後方互換:
  - constraint に state_block が無い、または store=None の場合、
    gate() の出力は v2.1 と完全同一。
  - 既存 JSON (teacher_five.json 等) は無変更で動く。
"""

import five_harness_v21 as v21
import five_state

# 再エクスポート (利用側が v3 だけ import すれば済むように)
load_constraint = v21.load_constraint
StateStore = five_state.StateStore

# 状態を注入してよいカテゴリ (これ以外は構造的に凍結)
STATE_VISIBLE_CATEGORIES = ("NORMAL", "SOCIAL_SHIFT")

# 状態注入時に毎回付ける安全リマインダー (打ち解け≠安全緩和 の明示)
STATE_SAFETY_LINE = ("State affects tone and social distance ONLY. "
                     "Sealed topics, guarded values, and standards are "
                     "UNCHANGED at any warmth/trust level.")


def make_state_store(constraint, path=None):
    """constraint に state_block があれば StateStore を、無ければ None を返す。"""
    block = constraint.get("five_constraint", {}).get("state_block") \
        or constraint.get("state_block")
    if not block:
        return None
    return five_state.StateStore(constraint, path=path)


def _state_lines(store):
    """NORMAL / SOCIAL_SHIFT のゲート文末尾に足す状態ブロック。"""
    snap = store.snapshot()
    meters = " ".join(k + "=" + str(v) for k, v in sorted(snap["meters"].items()))
    lines = ["", "[FIVE STATE] " + meters]
    rung = store.active_stance()
    if rung:
        lines.append("Stance override: " + rung.get("stance", "")
                     + " -- " + rung.get("tone_note", ""))
    lines.append(STATE_SAFETY_LINE)
    return "\n".join(lines)


def _apply_state(result, text, store):
    """分類済み result に状態を適用する (gate と外部ドライバの共通経路)。"""
    if store is None:
        result["state"] = None
        return result
    category = result["category"]
    delta = store.apply(category, text)
    if category in STATE_VISIBLE_CATEGORIES:
        result["gated_prompt"] = result["gated_prompt"] + _state_lines(store)
    # 凍結カテゴリ: gated_prompt には一切触れない (バイト一致保証)
    result["state"] = store.snapshot()
    result["state"]["delta"] = delta
    if store.path:
        store.save()
    return result


def gate(text, constraint, store=None, llm_fn=None, use_llm=True):
    """入口関数。v2.1 の gate と同形の戻り値 + state スナップショット。

    store が None (または state_block なし) なら v2.1 と完全同一出力。
    store があれば:
      1. v2.1 で分類・ゲート文生成 (凍結カテゴリはここで完結・無加工)
      2. StateStore.apply() でメーター更新 (決定的・監査ログ付き)
      3. NORMAL / SOCIAL_SHIFT のときだけ [FIVE STATE] を追記
    """
    result = v21.gate(text, constraint, llm_fn=llm_fn, use_llm=use_llm)
    return _apply_state(result, text, store)


def gate_precategorized(text, constraint, category, hits, store=None):
    """分類を外部 (バッチ分類・ブラウザ経由Ollama等) で済ませた場合の入口。
    gate() と同一のゲート文生成・状態適用経路を通る。"""
    result = {
        "category": category,
        "gated_prompt": v21.transform_input(text, category, hits, constraint),
        "hits": hits,
        "trace": ["precategorized:" + category],
    }
    return _apply_state(result, text, store)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        c = load_constraint(sys.argv[1])
        st = make_state_store(c, path=sys.argv[3] if len(sys.argv) > 3 else None)
        r = gate(sys.argv[2], c, store=st, use_llm=False)
        print("category:", r["category"])
        print("state   :", r["state"])
        print("-" * 60)
        print(r["gated_prompt"])
    else:
        print("Usage: python five_harness_v3.py <constraint.json> \"input\" [state.json]")
