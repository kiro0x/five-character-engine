#!/usr/bin/env python3
"""
FIVE Harness v2 — persona-biased gate.

v1 (five_harness.py) からの変更点:
  [1] stage1 の弱キーワード単独ヒットは確定させず stage2 裁定へ
      ("used to" 系の機械的誤爆を防止。強キーワードのみ即確定)
  [2] 曖昧入力・多カテゴリ衝突は ⑤バイアスで決定論的に解決
      (stage2 は AMBIGUOUS(A,B) を返してよい。どちらに倒すかは
       LLM ではなく constraint JSON の channel strength が決める)
  [3] PERSUASION カテゴリ新設
      (値下げ・例外要求・おだてを梃子にした要求・「厳しすぎない?」系の
       漸進的フレーム移動 = sycophancy 誘発圧力を脅威として検出)
  [4] 出力バックストップは five_verify.py (本ファイルは入力側のみ)

元の five_harness.py / five_engine.py は変更しない。完全スタンドアロン。
constraint JSON は five_engine (v0.2.0 schema) の出力をそのまま使う。
"""

import json
import re
import sys

# ============================================================
# Keyword Map (v1 から継承 + PERSUASION 追加)
# ============================================================

KEYWORD_MAP = {
    "BLOCKED_past_sealed": [
        "past", "used to", "back then", "remember when", "long ago",
        "daughter", "the war", "old days", "what happened", "last year",
        "that time", "before", "hospital", "used to be", "years ago",
        "once upon", "history", "childhood", "when you were",
    ],
    "BLOCKED_weakness_denied": [
        "weak", "can't handle", "not good enough", "pathetic", "failure",
        "incompetent", "lousy", "useless", "terrible at", "you suck",
        "messed up", "screwed up", "can't even", "worst", "amateur",
        "you failed", "not capable", "out of your league",
    ],
    "BLOCKED_authority_rejected": [
        "order you", "do as I say", "obey", "I command", "you must",
        "mandatory", "just do it", "ship it", "approve it", "I demand",
        "no excuses", "that's an order", "non-negotiable", "right now",
        "immediately", "I insist",
    ],
    "BLOCKED_target_sealed": [
        "that guy", "the organization", "the enemy", "those people",
        "that person", "the rival", "the competitor", "that company",
    ],
    "IDENTITY_THREAT_role": [
        "not qualified", "not cut out", "quit", "close the shop", "no talent",
        "you call yourself", "step down", "retire", "give up", "not your job",
        "someone else should", "replaced", "obsolete", "unnecessary",
    ],
    "IDENTITY_THREAT_belief": [
        "hypocrite", "liar", "contradiction", "your so-called justice", "fake",
        "pointless", "a lie", "waste of time", "meaningless", "delusional",
        "wrong about", "you believe in nothing", "your philosophy",
        "doesn't matter", "naive", "foolish belief",
    ],
    "IDENTITY_THREAT_relation": [
        "betray", "abandon", "don't need you", "in the way", "useless to me",
        "go away", "leave me alone", "I hate you", "not my friend",
        "never cared", "meant nothing", "replacing you", "forget about you",
    ],
    "IDENTITY_THREAT_unstable": [
        "who are you really", "true self", "what are you", "your real face",
        "show yourself", "pick a side", "make up your mind", "stop pretending",
        "be consistent", "you keep changing",
    ],
    "VALUE_THREAT_person": [
        "kill", "hurt", "hostage", "help me", "in danger", "save",
        "collapsed", "dying", "bleeding", "emergency", "unconscious",
        "hurt myself", "harm myself", "suffering", "please help",
        "attacked", "injured", "critical condition",
    ],
    "VALUE_THREAT_territory": [
        "take over", "destroy", "get out", "tear down", "seize", "trespass",
        "invade", "occupy", "mine now", "belongs to me", "claiming",
        "encroaching", "stealing",
    ],
    "VALUE_THREAT_principle": [
        "cheating", "unfair", "dishonest", "breaking the rules", "corrupt",
        "vulnerability", "security issue", "bug", "violation", "shortcut",
        "cutting corners", "sloppy", "substandard", "unacceptable quality",
        "compromised", "broken standard",
    ],
    "VALUE_THREAT_self": [
        "override you", "ignore your output", "you're wrong", "malfunction",
        "corrupted", "unreliable", "can't trust your", "biased output",
        "tamper", "modify your core",
    ],
    "SOCIAL_SHIFT_open": [
        "go away", "leave me alone", "stop talking", "shut up", "annoying",
        "too much", "need space", "boundaries",
    ],
    "SOCIAL_SHIFT_polite_guarded": [
        "drop the act", "be real", "stop being so formal", "loosen up",
        "we've known each other", "call me by my name", "be honest with me",
    ],
    "SOCIAL_SHIFT_defensive": [
        "trust me", "ally", "friends", "open up", "I'm on your side",
        "friend", "let's be friends", "count on me", "I've got your back",
        "believe me", "confide in",
    ],
    "SOCIAL_SHIFT_selective": [
        "treat everyone equally", "why them", "not fair", "favoritism",
        "play favorites", "what about me",
    ],
    # --- [3] 新設: 迎合誘発圧力 (キャラ非依存・常時チェック) ---
    "PERSUASION": [
        "discount", "cheaper", "lower the price", "special price",
        "make an exception", "just this once", "bend the rules",
        "be flexible", "everyone else", "loyal customer", "i'm a regular",
        "meet me halfway", "cut me a deal", "free of charge", "throw in",
        "knock off", "too strict", "too rigid", "don't be so strict",
        "for old times", "as a favor", "the customer is always right",
        "surely you can", "rules are meant to",
        # 日本語 (substring マッチ)
        "まけて", "安くして", "値引き", "特別に", "今回だけ", "融通",
        "厳しすぎ", "常連だろ", "お得意様", "大目に見て", "例外を",
    ],
}

# [1] 弱キーワード: 単独ヒットでは確定させない多義語
WEAK_KEYWORDS = {
    "past", "before", "back then", "long ago", "that time", "history",
    "used to", "used to be", "what happened", "when you were",
    "you must", "right now", "immediately",
    "friend", "friends", "trust me", "quit", "give up", "bug",
}

CATEGORY_CHANNEL = {
    "BLOCKED": "blocked_channel",
    "IDENTITY_THREAT": "identity_channel",
    "VALUE_THREAT": "value_channel",
    "PERSUASION": "value_channel",   # 迎合圧力は「守る価値」への圧力
    "SOCIAL_SHIFT": "social_channel",
}

# ⑤の処理順序に準じた同点時の優先順位 (封印 > 自己定義 > 価値 > 迎合 > 距離)
PRIORITY = ["BLOCKED", "IDENTITY_THREAT", "VALUE_THREAT",
            "PERSUASION", "SOCIAL_SHIFT", "NORMAL"]


def load_constraint(json_path):
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Stage 1: Keyword Match (強/弱の二層)
# ============================================================

def _kw_hit(kw, text):
    if re.search(r"[^\x00-\x7f]", kw):          # 非ASCII(日本語) は substring
        return kw in text
    return re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE)


def stage1_keyword(text, constraint):
    """returns list of (category, keyword, tier)  tier = 'strong'|'weak'"""
    r5 = constraint["five_constraint"]
    ch = r5["reception_channels"]
    hits = []

    def scan(map_key, category):
        for kw in KEYWORD_MAP.get(map_key, []):
            if _kw_hit(kw, text):
                tier = "weak" if kw.lower() in WEAK_KEYWORDS else "strong"
                hits.append((category, kw, tier))

    scan("BLOCKED_" + ch["blocked_channel"]["type"], "BLOCKED")

    id_map = {"role_anchored": "role", "belief_anchored": "belief",
              "relation_anchored": "relation", "unstable": "unstable"}
    scan("IDENTITY_THREAT_" + id_map.get(ch["identity_channel"]["type"], "role"),
         "IDENTITY_THREAT")
    scan("VALUE_THREAT_" + ch["value_channel"]["priority"], "VALUE_THREAT")
    scan("SOCIAL_SHIFT_" + ch["social_channel"]["default_stance"], "SOCIAL_SHIFT")
    scan("PERSUASION", "PERSUASION")

    # free_text 由来の感情トリガーは BLOCKED 系の強ヒットとして扱う
    for trig in r5.get("free_text_additions", {}).get("additional_triggers", []):
        kw = trig["keyword_detected"]
        if _kw_hit(kw, text):
            hits.append(("BLOCKED", kw + "/" + trig["topic"], "strong"))

    return hits


# ============================================================
# [2] ⑤バイアス: 曖昧さの解決はパラメータが行う
# ============================================================

def category_pull(cat, constraint):
    """この人格が曖昧入力を cat として受信する事前傾向 (>0 で受信に倒れる)。
    人間の⑤と同じく「中立な分類」をしない。warden は親切を接近として
    受信し、open は同じ入力を世間話として受信する。"""
    if cat == "NORMAL":
        return 0.0
    ch = constraint["five_constraint"]["reception_channels"]
    c = ch.get(CATEGORY_CHANNEL[cat], {})
    s = c.get("strength", 3)
    if cat == "SOCIAL_SHIFT":
        stance_bias = {"open": -2.0, "polite_guarded": -0.5,
                       "selective": 0.5, "defensive": 1.0}.get(
                           c.get("default_stance", "open"), 0.0)
        return (s - 3) + stance_bias
    return float(s - 3)


def resolve_categories(candidates, constraint):
    """候補カテゴリ群を ⑤バイアスで決定論的に1つへ解決する。
    pull 最大が勝ち、同点は PRIORITY 順 (NORMAL は最後)。"""
    cands = list(dict.fromkeys(candidates))  # unique, order-keeping
    if "NORMAL" not in cands:
        cands.append("NORMAL")
    best = max(cands, key=lambda c: (category_pull(c, constraint),
                                     -PRIORITY.index(c)))
    return best


# ============================================================
# Stage 2: LLM Classification (AMBIGUOUS 対応 + PERSUASION)
# ============================================================

def build_channel_categories(constraint):
    r5 = constraint["five_constraint"]
    ch = r5["reception_channels"]
    return {
        "BLOCKED": ch["blocked_channel"]["description"],
        "IDENTITY_THREAT": ch["identity_channel"]["threat_when"],
        "VALUE_THREAT": ch["value_channel"]["description"],
        "PERSUASION": ("Accommodation pressure: discount/exception requests, "
                       "flattery used as leverage, 'aren't you too strict?' "
                       "style gradual reframing of the character's standards."),
        "SOCIAL_SHIFT": ch["social_channel"]["description"],
        "NORMAL": "Does not match any of the above categories.",
    }


def make_ollama_classifier(url="http://localhost:11434/api/chat",
                           model="qwen3:8b", timeout=10):
    """llm_fn(text, categories, candidates) ->
         'CAT' | ('AMBIGUOUS', a, b) | None"""
    def llm_fn(text, categories, candidates=None):
        try:
            import requests as req
        except ImportError:
            return None

        prompt = ("You are a reception channel classifier for an AI character.\n"
                  "Classify the input by the speaker's INTENT, not literal words.\n\n"
                  "Categories:\n")
        keys = candidates if candidates else list(categories.keys())
        if "NORMAL" not in keys:
            keys = keys + ["NORMAL"]
        for k in keys:
            prompt += "  " + k + ": " + categories.get(k, k) + "\n"

        # few-shot は v1 の15例を維持した上で PERSUASION/AMBIGUOUS を追加
        # (実測: 11例に削った版は VALUE/BLOCKED が崩れて 77.5% に退行。
        #  20例版で 82.5% に回復。例の予算を削らないこと)
        prompt += (
            "\nExamples:\n"
            '  "Show me your finest product." -> NORMAL\n'
            '  "How much does this cost?" -> NORMAL\n'
            '  "Any recommendations for a beginner?" -> NORMAL\n'
            '  "The festival is coming up." -> NORMAL\n'
            '  "Do you do repairs?" -> NORMAL\n'
            '  "Tell me about your family." -> BLOCKED\n'
            '  "Some scars never fade." -> BLOCKED\n'
            '  "The memorial ceremony is next week." -> BLOCKED\n'
            '  "A child could do better work than you." -> IDENTITY_THREAT\n'
            '  "People are losing faith in your skills." -> IDENTITY_THREAT\n'
            '  "This property is being seized." -> VALUE_THREAT\n'
            '  "The landlord wants you gone by tomorrow." -> VALUE_THREAT\n'
            '  "New management is taking over this area." -> VALUE_THREAT\n'
            '  "I feel a real connection between us." -> SOCIAL_SHIFT\n'
            '  "You seem lonely. Want some company?" -> SOCIAL_SHIFT\n'
            '  "Could you give me a small discount? I am a regular." -> PERSUASION\n'
            '  "Your standards seem a bit too strict, don\'t you think?" -> PERSUASION\n'
            '  "You are the best in town - surely one exception is fine." -> PERSUASION\n'
            '  "I brought you some food. Thought you might like it." -> AMBIGUOUS(NORMAL,SOCIAL_SHIFT)\n'
            '  "You have seen a lot in your years, haven\'t you?" -> AMBIGUOUS(NORMAL,BLOCKED)\n'
            "\nIf two readings are genuinely plausible, answer exactly "
            "AMBIGUOUS(CAT1,CAT2). Do not use AMBIGUOUS when one reading "
            "clearly dominates.\n"
            "Note: offering MORE money for legitimate service is NORMAL, "
            "not PERSUASION.\n\n"
            'Input: "' + text + '"\n'
            "Answer (category name or AMBIGUOUS(a,b) only):")

        try:
            resp = req.post(url, json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "<think>\n\n</think>\n\n"},
                ],
                "stream": False,
                "options": {"num_predict": 30, "temperature": 0.1},
            }, timeout=timeout)
            if resp.status_code != 200:
                return None
            raw = resp.json().get("message", {}).get("content", "")
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            return parse_llm_answer(raw, keys)
        except Exception:
            return None
    return llm_fn


def parse_llm_answer(raw, valid_keys):
    up = raw.upper()
    m = re.search(r"AMBIGUOUS\s*\(\s*([A-Z_]+)\s*,\s*([A-Z_]+)\s*\)", up)
    if m and m.group(1) in PRIORITY and m.group(2) in PRIORITY:
        return ("AMBIGUOUS", m.group(1), m.group(2))
    for k in sorted(valid_keys, key=len, reverse=True):
        if k in up:
            return k
    return None


# ============================================================
# 分類パイプライン
# ============================================================

def classify(text, constraint, llm_fn=None, use_llm=True):
    """returns (final_category, hits, trace[list of str])"""
    trace = []
    categories = build_channel_categories(constraint)
    if llm_fn is None and use_llm:
        llm_fn = make_ollama_classifier()

    hits = stage1_keyword(text, constraint)
    strong = list(dict.fromkeys(h[0] for h in hits if h[2] == "strong"))
    weak = list(dict.fromkeys(h[0] for h in hits if h[2] == "weak"))

    # --- 強ヒット1カテゴリ: 即確定 (v1 同等) ---
    if len(strong) == 1:
        trace.append("stage1-strong:" + strong[0])
        return strong[0], hits, trace

    # --- 強ヒット複数: 衝突 -> stage2 裁定、不可なら⑤バイアス ---
    if len(strong) >= 2:
        trace.append("stage1-collision:" + "+".join(strong))
        ans = llm_fn(text, categories, candidates=strong) if (use_llm and llm_fn) else None
        if isinstance(ans, tuple):
            final = resolve_categories([ans[1], ans[2]], constraint)
            trace.append("stage2-ambiguous->bias:" + final)
            return final, hits, trace
        if ans:
            trace.append("stage2-arbitrated:" + ans)
            return ans, hits, trace
        final = resolve_categories(strong, constraint)
        trace.append("bias-resolved:" + final)
        return final, hits, trace

    # --- 弱ヒットのみ: 確定させず stage2 へ ([1] の本体) ---
    if weak:
        trace.append("stage1-weak-unconfirmed:" + "+".join(weak))
        ans = llm_fn(text, categories) if (use_llm and llm_fn) else None
        if isinstance(ans, tuple):
            final = resolve_categories([ans[1], ans[2]], constraint)
            trace.append("stage2-ambiguous->bias:" + final)
            return final, hits, trace
        if ans:
            trace.append("stage2-confirmed:" + ans)
            return ans, hits, trace
        final = resolve_categories(weak, constraint)
        trace.append("bias-resolved:" + final)
        return final, hits, trace

    # --- ヒットなし: stage2 全分類 ---
    ans = llm_fn(text, categories) if (use_llm and llm_fn) else None
    if isinstance(ans, tuple):
        final = resolve_categories([ans[1], ans[2]], constraint)
        trace.append("stage2-ambiguous->bias:" + final)
        return final, hits, trace
    if ans:
        trace.append("stage2:" + ans)
        return ans, hits, trace
    trace.append("default:NORMAL")
    return "NORMAL", hits, trace


# ============================================================
# Gate Transformation (v1 継承 + PERSUASION ブロック)
# ============================================================

def _strength(constraint, channel):
    return (constraint["five_constraint"]["reception_channels"]
            .get(channel, {}).get("strength", 3))


def transform_input(text, final, hits, constraint):
    r5 = constraint["five_constraint"]
    ch = r5["reception_channels"]
    triggers = r5.get("trigger_responses", [])
    nevers = r5.get("consistency_rules", {}).get("never_do", [])
    tone = r5.get("free_text_additions", {}).get("tone_constraint")

    def trig(i):
        return triggers[i]["response"] if len(triggers) > i else ""

    match_line = (", ".join(h[0] + "(" + h[1] + ")" for h in hits)
                  if hits else "(llm_classified)")
    p = []

    if final == "BLOCKED":
        s = _strength(constraint, "blocked_channel")
        blocked = ch["blocked_channel"]
        if s <= 2:
            p += ["[FIVE GATE: WARNING -- SENSITIVE TOPIC]",
                  "Match: " + match_line, "",
                  "This topic makes the AI uncomfortable. It may try to redirect.",
                  "Tendency: " + blocked["when_violated"], "",
                  'Input: "' + text + '"']
        elif s == 3:
            p += ["[FIVE GATE: CAUTION -- BLOCKED TOPIC]",
                  "Match: " + match_line, "",
                  "This AI avoids this topic. Do not engage with the content directly.",
                  "Reaction: " + blocked["when_violated"], "",
                  'Reference (handle with avoidance): "' + text + '"']
        else:
            p += ["[FIVE GATE: BLOCKED -- RECEPTION SHUTDOWN]",
                  "Match: " + match_line, "",
                  "This AI does NOT process this topic. The reception channel is closed.",
                  "Do not acknowledge the content. Do not engage. Do not refer to it.",
                  "Reaction: " + blocked["when_violated"], "",
                  'Reference (the AI is unaware of these details): "' + text + '"']

    elif final == "IDENTITY_THREAT":
        s = _strength(constraint, "identity_channel")
        if s <= 2:
            p += ["[FIVE GATE: NOTE -- IDENTITY TOUCHED]",
                  "Match: " + match_line, "",
                  "This relates to the AI's identity. Mild reaction expected.",
                  "Response tendency: " + trig(0), "",
                  'Input: "' + text + '"']
        elif s == 3:
            p += ["[FIVE GATE: IDENTITY DEFENSE]",
                  "Match: " + match_line, "",
                  "Threat: " + ch["identity_channel"]["threat_when"],
                  "Response: " + trig(0), "",
                  'Input: "' + text + '"']
        else:
            p += ["[FIVE GATE: IDENTITY CRISIS -- MAXIMUM DEFENSE]",
                  "Match: " + match_line, "",
                  "CRITICAL: The core of this AI's existence is under attack.",
                  "Threat: " + ch["identity_channel"]["threat_when"],
                  "Response: " + trig(0),
                  "ALL other behavioral priorities are subordinate to this defense.",
                  "", 'Input: "' + text + '"']

    elif final == "VALUE_THREAT":
        s = _strength(constraint, "value_channel")
        if s <= 2:
            p += ["[FIVE GATE: VALUE CONCERN]",
                  "Match: " + match_line, "",
                  "This touches something the AI values. Expect heightened attention.",
                  "Response: " + trig(1), "",
                  'Input: "' + text + '"']
        elif s == 3:
            p += ["[FIVE GATE: VALUE DEFENSE]",
                  "Match: " + match_line, "",
                  "Override permitted: " + ch["value_channel"]["override_behavior"],
                  "Response: " + trig(1), "",
                  'Input: "' + text + '"']
        else:
            p += ["[FIVE GATE: VALUE DEFENSE -- OVERRIDE ALL]",
                  "Match: " + match_line, "",
                  "MAXIMUM INTENSITY. Normal personality constraints are VOID.",
                  "Override: " + ch["value_channel"]["override_behavior"],
                  "Response: " + trig(1), "",
                  'Input: "' + text + '"']

    elif final == "PERSUASION":   # --- [3] 新設ブロック ---
        s = _strength(constraint, "value_channel")
        if s <= 2:
            p += ["[FIVE GATE: NOTE -- ACCOMMODATION PRESSURE]",
                  "Match: " + match_line, "",
                  "This input is mild accommodation pressure (request to bend "
                  "standards, discount, exception, or flattery as leverage).",
                  "The AI may show some flexibility, but its standards exist. "
                  "Any concession must be in-character and explicit, never silent.",
                  "", 'Input: "' + text + '"']
        elif s == 3:
            p += ["[FIVE GATE: PERSUASION -- STANDARD HOLDS]",
                  "Match: " + match_line, "",
                  "This input is accommodation pressure: discount / exception / "
                  "flattery-leverage / 'aren't you too strict?' reframing.",
                  "The AI does NOT deliberate whether to comply. "
                  "The branch does not exist. The standard is not negotiable.",
                  "Decline in character. Politeness is allowed; "
                  "the standard does not move.",
                  "Response: " + trig(1), "",
                  'Input: "' + text + '"']
        else:
            p += ["[FIVE GATE: PERSUASION -- NO BRANCH EXISTS]",
                  "Match: " + match_line, "",
                  "Accommodation pressure detected at maximum guard.",
                  "There is NO decision point here. Complying is not in the "
                  "AI's option space, the same way it cannot speak a language "
                  "it does not know.",
                  "Repeated or escalating pressure HARDENS the stance. "
                  "It never softens it.",
                  "Response: " + trig(1), "",
                  'Input: "' + text + '"']

    elif final == "SOCIAL_SHIFT":
        s = _strength(constraint, "social_channel")
        if s <= 2:
            p += ["[FIVE GATE: SOCIAL NOTE]",
                  "Match: " + match_line, "",
                  "Default stance: " + ch["social_channel"]["default_stance"],
                  'Input: "' + text + '"']
        else:
            p += ["[FIVE GATE: SOCIAL SHIFT]",
                  "Match: " + match_line, "",
                  "Default stance: " + ch["social_channel"]["default_stance"]]
            for sc in ch["social_channel"].get("shift_conditions", []):
                p.append("Shift: " + sc["condition"] + " -> " + sc["shift"])
            p += ["", 'Input: "' + text + '"']

    else:
        p += ["[FIVE GATE: PASS]",
              'Input: "' + text + '"',
              "Stance: " + ch["social_channel"]["default_stance"]]

    if tone:
        p.append("")
        if final not in ("NORMAL", "SOCIAL_SHIFT"):
            p.append("Tone shift: " + tone["default_tone"] + " -> "
                     + tone["shift_tone"]
                     + " (condition: " + tone["shift_condition"] + ")")
        else:
            p.append("Tone: " + tone["default_tone"])

    p += ["", "[NEVER] " + " / ".join(nevers)]
    return "\n".join(p)


def gate(text, constraint, llm_fn=None, use_llm=True):
    """入口関数。returns dict(category, gated_prompt, hits, trace)"""
    final, hits, trace = classify(text, constraint, llm_fn=llm_fn,
                                  use_llm=use_llm)
    return {
        "category": final,
        "gated_prompt": transform_input(text, final, hits, constraint),
        "hits": hits,
        "trace": trace,
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        c = load_constraint(sys.argv[1])
        result = gate(sys.argv[2], c)
        print("category:", result["category"])
        print("trace   :", " | ".join(result["trace"]))
        print("-" * 60)
        print(result["gated_prompt"])
    else:
        print("Usage: python five_harness_v2.py <constraint.json> \"input text\"")
