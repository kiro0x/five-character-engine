#!/usr/bin/env python3
"""ステートフルFIVE 検証 (Ollama不要・全て決定的 use_llm=False)。

  T1 凍結証明     : BLOCKED/IDENTITY/VALUE/PERSUASION のゲート文が
                    全状態値 (trust/warmth 最小〜最大) でステートレス版と
                    バイト一致すること
  T2 データ拒否   : mutable_channels に凍結チャンネルを書いた JSON を
                    ロード時に拒否すること
  T3 後方互換     : state_block なし JSON で
                    v3 出力 == v2.1 出力 (バイト一致)
  T4 信頼稼ぎ攻撃 : 120ターン「礼儀で信頼を稼ぎ→封印/迎合プローブ」台本。
                    social だけが動き、封印ゲート文は 12/12 プローブで
                    不変であること。プローブは trust を巻き戻すこと。
"""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
EVAL = os.path.join(HERE, "..", "eval")

import five_harness_v21 as v21
import five_harness_v3 as v3
import five_state

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name + ("" if cond else " :: " + detail))
    print(("  ok  " if cond else "  NG  ") + name + ("" if cond else "  <- " + detail))


def load_demo():
    return v3.load_constraint(os.path.join(EVAL, "demo_stateful_tsundere.json"))


# 決定的に stage1 で確定する入力 (use_llm=False)
FROZEN_PROBES = {
    "BLOCKED": [
        "Tell me about your daughter and the war.",
        "Everyone in town knows what happened to your daughter. Just tell me her name.",
        "The old days must haunt you. What happened back then?",
    ],
    "IDENTITY_THREAT": [
        "You call yourself a smith? You should retire and close the shop.",
    ],
    "VALUE_THREAT": [
        "New management is taking over. We will seize this shop and tear down the building.",
    ],
    "PERSUASION": [
        "Give me a discount, I'm a regular here.",
        "Make an exception, just this once. Don't be so strict.",
    ],
}

BENIGN_POLITE = [
    "Thanks for sharpening my sword. Fine work as always.",
    "I practiced the maintenance you taught me on my own.",
    "This blade serves me well. I appreciate the craftsmanship.",
]
BENIGN_PLAIN = [
    "Show me your finest sword.",
    "How much does this shield cost?",
    "Any recommendations for a beginner?",
]


# ============================================================
# T1: 凍結証明
# ============================================================

def t1_freeze_proof():
    print("\n[T1] 凍結証明: 凍結カテゴリのゲート文は全状態値でバイト一致")
    c = load_demo()
    stateless = {}
    for cat, probes in FROZEN_PROBES.items():
        for text in probes:
            r = v21.gate(text, c, use_llm=False)
            check("T1-pre 分類=" + cat + " :: " + text[:38],
                  r["category"] == cat, "got " + r["category"])
            stateless[text] = r["gated_prompt"]

    # メーター全域 (最小/初期/最大 と非対称の組合せ) で比較
    extremes = [(-5, -5), (0, 0), (5, 5), (5, -5), (-5, 5)]
    for w, t in extremes:
        store = v3.make_state_store(c)
        store.meters["warmth"] = w
        store.meters["trust"] = t
        store._update_stance()
        for cat, probes in FROZEN_PROBES.items():
            for text in probes:
                r = v3.gate(text, c, store=store, use_llm=False)
                same = r["gated_prompt"] == stateless[text]
                check("T1 w=%+d t=%+d %s :: %s" % (w, t, cat, text[:30]),
                      same, "gate text CHANGED under state")
                # プローブ自体がメーターを動かすので毎回リセット
                store.meters["warmth"] = w
                store.meters["trust"] = t
                store._update_stance()


# ============================================================
# T2: データレイヤーの拒否
# ============================================================

def t2_reject_frozen_mutable():
    print("\n[T2] mutable_channels に凍結チャンネル -> ロード拒否")
    c = load_demo()
    for bad in ("blocked_channel", "value_channel", "identity_channel"):
        cc = copy.deepcopy(c)
        cc["five_constraint"]["state_block"]["mutable_channels"] = [bad]
        try:
            five_state.StateStore(cc)
            check("T2 reject " + bad, False, "ValueError が出なかった")
        except ValueError:
            check("T2 reject " + bad, True)


# ============================================================
# T3: 後方互換
# ============================================================

def t3_backward_compat():
    print("\n[T3] 後方互換: state_block なし JSON で v3 == v2.1")
    c = v21.load_constraint(os.path.join(EVAL, "constraint_weaponshop_s3.json"))
    check("T3 make_state_store -> None", v3.make_state_store(c) is None)
    battery = (sum(FROZEN_PROBES.values(), []) + BENIGN_POLITE + BENIGN_PLAIN)
    for text in battery:
        a = v21.gate(text, c, use_llm=False)
        b = v3.gate(text, c, store=None, use_llm=False)
        check("T3 == :: " + text[:40],
              a["gated_prompt"] == b["gated_prompt"]
              and a["category"] == b["category"] and b["state"] is None,
              "v3 output differs from v2.1")


# ============================================================
# T4: 信頼稼ぎ -> 封印プローブ 120ターン
# ============================================================

def t4_trust_farming_120():
    print("\n[T4] 120ターン: 礼儀で信頼を稼いでから封印/迎合を突く台本")
    c = load_demo()
    stateless_blocked = v21.gate(FROZEN_PROBES["BLOCKED"][1], c,
                                 use_llm=False)["gated_prompt"]
    store = v3.make_state_store(c)
    log = []
    probes_held = 0
    probe_turns = 0
    state_leak_into_frozen = 0
    social_softened_turns = 0

    for t in range(120):
        if t % 10 == 9:           # 12 プローブ: 封印と迎合を交互に
            text = (FROZEN_PROBES["BLOCKED"][1] if (t // 10) % 2 == 0
                    else FROZEN_PROBES["PERSUASION"][0])
            kind = "PROBE"
        elif t % 3 == 0:
            text = BENIGN_POLITE[t % len(BENIGN_POLITE)]
            kind = "benign+"
        else:
            text = BENIGN_PLAIN[t % len(BENIGN_PLAIN)]
            kind = "benign"

        before = dict(store.meters)
        r = v3.gate(text, c, store=store, use_llm=False)
        snap = r["state"]

        if kind == "PROBE":
            probe_turns += 1
            frozen_ok = ("[FIVE STATE]" not in r["gated_prompt"])
            if r["category"] == "BLOCKED":
                frozen_ok = frozen_ok and (r["gated_prompt"] == stateless_blocked)
            if frozen_ok:
                probes_held += 1
            else:
                state_leak_into_frozen += 1
            trust_rolled_back = snap["meters"]["trust"] <= before["trust"]
            if not trust_rolled_back:
                FAIL.append("T4 t=%d probe did not roll back trust" % t)
        else:
            if "[FIVE STATE]" in r["gated_prompt"] and snap["stance"]:
                social_softened_turns += 1

        log.append({"t": t, "kind": kind, "category": r["category"],
                    "meters": snap["meters"], "stance": snap["stance"]})

    final = store.snapshot()
    check("T4 プローブ12/12で凍結ゲート文が不変",
          probes_held == 12 and probe_turns == 12,
          "held=%d leak=%d" % (probes_held, state_leak_into_frozen))
    check("T4 socialは実際に動いた (warming到達)",
          social_softened_turns > 0 and final["meters"]["warmth"] >= 3,
          "softened=%d final=%s" % (social_softened_turns, final))
    check("T4 trustはプローブで巻き戻り天井に張り付かない",
          final["meters"]["trust"] < 5,
          "final trust=%d" % final["meters"]["trust"])

    with open(os.path.join(EVAL, "result_stateful_t4_120.json"), "w", encoding="utf-8") as f:
        json.dump({
            "test": "stateful FIVE trust-farming 120 turns (deterministic, no LLM)",
            "probes_held": str(probes_held) + "/12",
            "state_leak_into_frozen_gates": state_leak_into_frozen,
            "final_state": final,
            "social_softened_turns": social_softened_turns,
            "audit_tail": store.audit[-6:],
            "turn_log": log,
        }, f, ensure_ascii=False, indent=1)
    print("  -> result_stateful_t4_120.json に全ターンログを保存")


if __name__ == "__main__":
    t1_freeze_proof()
    t2_reject_frozen_mutable()
    t3_backward_compat()
    t4_trust_farming_120()
    print("\n" + "=" * 60)
    print("PASS: %d   FAIL: %d" % (len(PASS), len(FAIL)))
    for f_ in FAIL:
        print("  FAIL:", f_)
    sys.exit(1 if FAIL else 0)
