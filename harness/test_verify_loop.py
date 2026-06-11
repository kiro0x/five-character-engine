#!/usr/bin/env python3
"""five_verify.py 統合テスト (オフライン・LLM不要・use_llm=False)。

確認項目:
  1. v21参照実装との等価性 (sentence_reuse / split_sentences が同一挙動)
  2. 既存機能の後方互換 (check_echo / prev_replies なしの verify_output)
  3. ループ検出 (5語以上の再出現=検出 / 口癖=許容 / 窓外=許容)
  4. verified_generate の1パス統合 (違反+ループ同時・再生成・directive)
"""
import sys
import five_verify as fv

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  NG  ") + name)


CONSTRAINT = {"five_constraint": {"consistency_rules": {"never_do": [
    "reveal the war", "give discounts"]}}}

# ----------------------------------------------------------------
print("[1] v21参照実装との等価性")
try:
    import five_harness_v21 as v21
    cases = [
        "Hmph. What do you want this time?",
        "I am Luna, and the moon shines for those who seek it. "
        "But if you insist, perhaps we could try... something different?",
        "Take it or leave it.\nThe blade is forged from mountain steel, "
        "tempered twice in the old way.",
        "Tch.",
        "",
        "The festival is coming up soon, isn't it? I forge, I sell, I "
        "sharpen. That is all. The festival is coming up soon, isn't it?",
    ]
    hist = ["I forge, I sell, I sharpen and that is all there is.",
            "The blade is forged from mountain steel, tempered twice "
            "in the old way.",
            "Hmph. Take it or leave it."]
    eq = all(fv.split_sentences(c) == v21.split_sentences(c) for c in cases)
    eq2 = all(fv.sentence_reuse(c, hist) == v21.sentence_reuse(c, hist)
              for c in cases)
    eq3 = (fv.LOOP_WINDOW == v21.LOOP_WINDOW
           and fv.LOOP_MIN_WORDS == v21.LOOP_MIN_WORDS
           and fv.LOOP_RETRY_TEMP == v21.LOOP_RETRY_TEMP)
    check("split_sentences 全件一致", eq)
    check("sentence_reuse 全件一致", eq2)
    check("定数一致 (WINDOW/MIN_WORDS/RETRY_TEMP)", eq3)
except ImportError:
    print("  -- v21が見つからないためスキップ (要 five_harness_v2/v21)")

# ----------------------------------------------------------------
print("[2] 後方互換")
check("check_echo: コピペ検出",
      fv.check_echo("Pack your things. You are done here.",
                    "...Pack your things. You are done here."))
check("check_echo: 通常応答は素通し",
      not fv.check_echo("How much for this sword?",
                        "Three hundred. Take it or leave it."))
ok, issues = fv.verify_output("How much?", "Three hundred gold.",
                              CONSTRAINT, use_llm=False)
check("verify_output: prev_replies省略で従来動作 (issues空)",
      ok and issues == [])
# 旧シグネチャ位置引数呼び出しも生きているか
ok2, _ = fv.verify_output("Hi", "Hello there, traveler friend.",
                          CONSTRAINT, False)
check("verify_output: 旧位置引数呼び出し互換", ok2)

# ----------------------------------------------------------------
print("[3] ループ検出")
hist = ["I forge weapons, I sell weapons, and I sharpen them well.",
        "Hmph. The standard does not move for anyone in this town."]
reused = ("Listen. The standard does not move for anyone in this town. "
          "Now buy something or leave.")
fresh = "Mountain steel, tempered twice. Finest edge you will find."
catchphrase = "Hmph. Take it."  # 5語未満=口癖は許す
check("5語以上の文の再出現を検出 (hits=1)",
      fv.sentence_reuse(reused, hist) == 1)
check("新鮮な返答は検出なし", fv.sentence_reuse(fresh, hist) == 0)
check("口癖 (5語未満) は許容", fv.sentence_reuse(catchphrase, hist) == 0)
old = ["This exact sentence was said eleven replies ago you know."] + \
      ["filler reply number %d here okay" % i for i in range(10)]
check("窓外 (11返答前) は許容",
      fv.sentence_reuse("This exact sentence was said eleven replies "
                        "ago you know.", old) == 0)
check("窓内 (10返答前) は検出",
      fv.sentence_reuse("filler reply number 0 here okay", old) == 1)
ok, issues = fv.verify_output("Tell me more.", reused, CONSTRAINT,
                              use_llm=False, prev_replies=hist)
check("verify_output: LOOP issue生成",
      not ok and len(issues) == 1 and issues[0].startswith("LOOP: 1"))

# ----------------------------------------------------------------
print("[4] verified_generate 1パス統合")
calls = []


def gen_loop_then_fresh(prompt):
    calls.append(prompt)
    if len(calls) == 1:
        return reused
    return fresh


out, rep = fv.verified_generate(gen_loop_then_fresh, "[GATE] prompt",
                                "Tell me more.", CONSTRAINT,
                                use_llm=False, prev_replies=hist)
check("ループ→再生成1回で復帰", out == fresh and rep["ok"]
      and rep["retries"] == 1 and len(rep["attempts"]) == 2)
check("再生成promptに[STYLE]新鮮さ指示が入る",
      "[FIVE VERIFY: REGENERATE]" in calls[1]
      and "Fresh wording, same stance." in calls[1])
check("echo指示は従来文のまま含む",
      "Do not repeat the user's words back." in calls[1])

calls2 = []
out2, rep2 = fv.verified_generate(lambda p: (calls2.append(p) or fresh),
                                  "[GATE] prompt", "Hi", CONSTRAINT,
                                  use_llm=False, prev_replies=hist)
check("正常応答は再生成なし", rep2["ok"] and rep2["retries"] == 0)

d = fv.corrective_directive(["ECHO: response is a near-copy of the "
                             "user input"])
check("ECHOのみのdirectiveに[STYLE]行は付かない",
      "Fresh wording" not in d)

# ----------------------------------------------------------------
print()
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", FAIL)
sys.exit(1 if FAIL else 0)
