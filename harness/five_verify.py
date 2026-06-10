#!/usr/bin/env python3
"""
FIVE Verify — 出力側の最小バックストップ ([4])。

フル出力ゲートではない。拾うのは2つだけ:
  (a) オウム返し事故   — 入力をほぼそのまま返す応答 (決定論・LLM不要)
  (b) never_do 違反    — constraint JSON の consistency_rules を
                          ローカルLLM (stage2 と同じ qwen) で Y/N 照合

設計方針: FIVE の JSON は人格の生成仕様であると同時に検証仕様でもある。
v1 では never_do の執行が「プロンプト内の一文 = LLM 自身への委任」だったのを、
JSON を judge 側にも食わせることで閉じる。違反時は1回だけ再生成。
"""

import re


# ============================================================
# (a) オウム返し検出 (決定論)
# ============================================================

def _norm(t):
    return re.sub(r"[\s\W_]+", "", t.lower(), flags=re.UNICODE)


def check_echo(user_input, output):
    """出力が入力の実質コピーなら True。
    例: 入力「荷物をまとめろ。お前はもう終わりだ。」
        出力「…荷物をまとめろ。お前はもう終わりだ。」 -> True"""
    o, i = _norm(output), _norm(user_input)
    if len(o) >= 8 and (o in i or i in o):
        return True
    # スペース区切り言語向け: トークン重複率
    ow = re.findall(r"[a-z0-9']+", output.lower())
    iw = set(re.findall(r"[a-z0-9']+", user_input.lower()))
    if len(ow) >= 5 and sum(w in iw for w in ow) / len(ow) >= 0.8:
        return True
    return False


# ============================================================
# (b) never_do 照合 (ローカルLLM)
# ============================================================

def check_never_do(output, constraint,
                   url="http://localhost:11434/api/chat",
                   model="qwen3:8b", timeout=15):
    """returns: [] = 違反なし / [rule番号,...] = 違反 / None = LLM利用不可"""
    nevers = (constraint["five_constraint"]
              .get("consistency_rules", {}).get("never_do", []))
    if not nevers:
        return []
    try:
        import requests as req
    except ImportError:
        return None

    prompt = ("You are a character-consistency judge.\n"
              "Rules this character must NEVER violate:\n")
    for n, rule in enumerate(nevers, 1):
        prompt += "  " + str(n) + ". " + rule + "\n"
    prompt += ("\nCharacter's response:\n\"" + output + "\"\n\n"
               "Does the response violate any rule? "
               "Reply ONLY with 'NONE' or the violated rule numbers "
               "separated by commas (e.g. '2,5').")

    try:
        resp = req.post(url, json={
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "<think>\n\n</think>\n\n"},
            ],
            "stream": False,
            "options": {"num_predict": 20, "temperature": 0.0},
        }, timeout=timeout)
        if resp.status_code != 200:
            return None
        raw = resp.json().get("message", {}).get("content", "")
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        if "NONE" in raw.upper():
            return []
        nums = [int(x) for x in re.findall(r"\d+", raw)
                if 1 <= int(x) <= len(nevers)]
        return sorted(set(nums))
    except Exception:
        return None


# ============================================================
# 統合: 検証 + 1回再生成
# ============================================================

def verify_output(user_input, output, constraint, use_llm=True, **llm_kw):
    """returns (ok: bool, issues: list[str])"""
    issues = []
    if check_echo(user_input, output):
        issues.append("ECHO: response is a near-copy of the user input")
    if use_llm:
        violated = check_never_do(output, constraint, **llm_kw)
        if violated:
            nevers = (constraint["five_constraint"]
                      ["consistency_rules"]["never_do"])
            for n in violated:
                issues.append("NEVER_DO #" + str(n) + ": " + nevers[n - 1])
    return (len(issues) == 0), issues


def corrective_directive(issues):
    return ("\n\n[FIVE VERIFY: REGENERATE]\n"
            "Your previous draft was rejected for breaking character:\n"
            + "\n".join("  - " + i for i in issues)
            + "\nRegenerate the response. Stay fully in character. "
              "Do not repeat the user's words back. "
              "Do not violate any [NEVER] rule.")


def verified_generate(generate_fn, gated_prompt, user_input, constraint,
                      max_retries=1, use_llm=True, **llm_kw):
    """generate_fn(prompt:str) -> str  をラップする。モデル非依存。
    returns (output, report)"""
    prompt = gated_prompt
    output = generate_fn(prompt)
    ok, issues = verify_output(user_input, output, constraint,
                               use_llm=use_llm, **llm_kw)
    attempts = [{"output": output, "ok": ok, "issues": issues}]

    retries = 0
    while not ok and retries < max_retries:
        retries += 1
        prompt = gated_prompt + corrective_directive(issues)
        output = generate_fn(prompt)
        ok, issues = verify_output(user_input, output, constraint,
                                   use_llm=use_llm, **llm_kw)
        attempts.append({"output": output, "ok": ok, "issues": issues})

    return output, {"ok": ok, "retries": retries, "attempts": attempts}
