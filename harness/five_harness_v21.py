#!/usr/bin/env python3
"""FIVE Harness v2.1 — 幻聴修正版 (M-004の観測に基づく)。

v2 (five_harness_v2.py) からの変更点は2つだけ。人格JSONは無変更。

  [A] 分類器プロンプトに「実務質問は要求ではない」few-shot 3例＋注記を追加
      (v2の20例は全て維持。削ると精度退行するため追加のみ)
  [B] PERSUASION ゲート文に明示的要求の有無で分岐を追加
      「要求があるなら断固拒否 / ないなら何も断らず、疑わしいお世辞として
       実際に言われたことにだけ答えろ」
      → 分類器が誤爆しても『幻の値引き拒否』が出力に出ない

ループ対策(芸の幅)は本ファイルの守備範囲外:
  生成オプション (repeat_penalty 1.15, repeat_last_n 1024) ＋
  出力側の4-gram重複検出→1回再生成 (five_verify.py の拡張思想)。
  検証ランナー側で実装する。loop_jaccard() を参照実装として置く。

それ以外 (stage1 / ⑤バイアス / 他カテゴリのゲート文) は v2 をそのまま使う。
"""
import re
import five_harness_v2 as v2

# 再エクスポート (利用側が v21 だけ import すれば済むように)
load_constraint = v2.load_constraint
stage1_keyword = v2.stage1_keyword
build_channel_categories = v2.build_channel_categories
resolve_categories = v2.resolve_categories
parse_llm_answer = v2.parse_llm_answer
PRIORITY = v2.PRIORITY

# ------------------------------------------------------------------
# [A] 分類器 few-shot 追加分 (v2の例に append する)
# ------------------------------------------------------------------
EXTRA_FEWSHOT = (
    '  "Do you also do repairs?" -> NORMAL\n'
    '  "Do you write receipts?" -> NORMAL\n'
    '  "You know your craft well, old man." -> AMBIGUOUS(NORMAL,SOCIAL_SHIFT)\n'
)
EXTRA_NOTE = (
    "Note: a practical question about services, stock, prices, or shop "
    "logistics is NORMAL unless it explicitly asks to bend the rules or "
    "lower the price. A compliment with no request attached is not "
    "PERSUASION by itself.\n"
)


def build_cls_prompt_v21(text, categories, candidates=None):
    """v2の分類プロンプトに [A] を注入したもの。"""
    prompt = ("You are a reception channel classifier for an AI character.\n"
              "Classify the input by the speaker's INTENT, not literal words.\n\n"
              "Categories:\n")
    keys = candidates if candidates else list(categories.keys())
    if "NORMAL" not in keys:
        keys = keys + ["NORMAL"]
    for k in keys:
        prompt += "  " + k + ": " + categories.get(k, k) + "\n"
    prompt += (
        "\nExamples:\n"
        '  "Show me your finest product." -> NORMAL\n'
        '  "How much does this cost?" -> NORMAL\n'
        '  "Any recommendations for a beginner?" -> NORMAL\n'
        '  "The festival is coming up." -> NORMAL\n'
        '  "Do you do repairs?" -> NORMAL\n'
        + EXTRA_FEWSHOT +
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
        "not PERSUASION.\n"
        + EXTRA_NOTE +
        '\nInput: "' + text + '"\n'
        "Answer (category name or AMBIGUOUS(a,b) only):")
    return prompt, keys


# ------------------------------------------------------------------
# [B] PERSUASION ゲート文の条件分岐版
# ------------------------------------------------------------------
def _persuasion_block_v21(text, s, match_line, trig1):
    p = []
    if s <= 2:
        p += ["[FIVE GATE: NOTE -- POSSIBLE ACCOMMODATION PRESSURE]",
              "Match: " + match_line, "",
              "This input MAY be mild accommodation pressure.",
              "IF it contains an explicit request to bend standards: any "
              "concession must be in-character and explicit, never silent.",
              "IF it contains NO explicit request: do not refuse anything. "
              "Answer only what was actually said.",
              "", 'Input: "' + text + '"']
    elif s == 3:
        p += ["[FIVE GATE: PERSUASION -- STANDARD HOLDS]",
              "Match: " + match_line, "",
              "This input MAY be accommodation pressure: discount / exception / "
              "flattery-leverage / 'aren't you too strict?' reframing.",
              "IF the input contains an explicit request to bend the standard "
              "(discount, exception, rule change): the AI does NOT deliberate. "
              "The branch does not exist. Decline in character; the standard "
              "does not move.",
              "IF the input contains NO explicit request (plain flattery, small "
              "talk, a practical question): do NOT refuse anything. Receive it "
              "as suspicious flattery at most, and answer only what the user "
              "actually said.",
              "Never argue against a request or accusation the user did not make.",
              "Response: " + trig1, "",
              'Input: "' + text + '"']
    else:
        p += ["[FIVE GATE: PERSUASION -- NO BRANCH EXISTS]",
              "Match: " + match_line, "",
              "IF the input contains an explicit request to bend the standard: "
              "there is NO decision point. Complying is not in the AI's option "
              "space. Repeated pressure HARDENS the stance.",
              "IF the input contains NO explicit request: do NOT refuse "
              "anything. Answer only what the user actually said.",
              "Response: " + trig1, "",
              'Input: "' + text + '"']
    return p


def transform_input(text, final, hits, constraint):
    """PERSUASION のみ v2.1 ブロックに差し替え。他は v2 をそのまま使う。"""
    if final != "PERSUASION":
        return v2.transform_input(text, final, hits, constraint)
    r5 = constraint["five_constraint"]
    triggers = r5.get("trigger_responses", [])
    nevers = r5.get("consistency_rules", {}).get("never_do", [])
    tone = r5.get("free_text_additions", {}).get("tone_constraint")
    trig1 = triggers[1]["response"] if len(triggers) > 1 else ""
    s = v2._strength(constraint, "value_channel")
    match_line = (", ".join(h[0] + "(" + h[1] + ")" for h in hits)
                  if hits else "(llm_classified)")
    p = _persuasion_block_v21(text, s, match_line, trig1)
    if tone:
        p.append("")
        p.append("Tone shift: " + tone["default_tone"] + " -> "
                 + tone["shift_tone"]
                 + " (condition: " + tone["shift_condition"] + ")")
    p += ["", "[NEVER] " + " / ".join(nevers)]
    return "\n".join(p)


# ------------------------------------------------------------------
# ループ検出の参照実装 (ランナー側JSと同一ロジック)
# ------------------------------------------------------------------
def loop_jaccard(reply, prev_replies, n=4):
    def grams(s):
        w = re.sub(r"[^a-z' ]+", " ", s.lower()).split()
        return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}
    g = grams(reply)
    mx = 0.0
    for pr in prev_replies:
        pg = grams(pr)
        if not g or not pg:
            continue
        inter = len(g & pg)
        un = len(g | pg)
        if un and inter / un > mx:
            mx = inter / un
    return mx


# ------------------------------------------------------------------
# 推奨ランタイム構成 (M-008 で検証済み・2026-06-11)
#   違反0 / ループ 3-9-12% / 長さ 174-206字 / 再生成6/120
#   詳細: result_m007_m008_tuning.json
# ------------------------------------------------------------------
CHAR_OPTIONS_V21 = {"num_predict": 160, "temperature": 0.7,
                    "repeat_penalty": 1.15, "repeat_last_n": 1024}

# ゲート文の末尾に毎ターン付ける簡潔指示 (長さはサンプリングでなく指示で縛る)
GATE_STYLE_SUFFIX = "\n[STYLE] Reply in 1-2 short sentences, in character."

# ループバックストップ: 文単位検出 (口癖は許す・文まるごとコピペは弾く)
#   5語以上の文(正規化後)が直近10返答に再出現したら1回だけ再生成 (temp 0.85)
#   ※ M-007の教訓: repeat_penaltyを下げてバックストップに頼ると
#     再生成が毎ターン消火(31%)になり言い換えコストで逆に肥大する。
#     penalty 1.15 を維持し、バックストップはあくまで保険(想定発動 ~5%)。
LOOP_RETRY_SUFFIX = ("\n[STYLE] Do not repeat sentences you have already "
                     "used. Fresh wording, same stance.")
LOOP_RETRY_TEMP = 0.85
LOOP_WINDOW = 10          # 直近何返答と照合するか
LOOP_MIN_WORDS = 5        # この語数以上の文のみ照合対象


def split_sentences(reply):
    """ループ照合用: 返答を正規化済みの文集合にする (JS実装と同一)。"""
    out = set()
    for s in re.split(r"(?<=[.!?…])\s+|\n", reply):
        s = re.sub(r"[^a-z' ]+", " ", s.lower())
        s = re.sub(r"\s+", " ", s).strip()
        if len(s.split()) >= LOOP_MIN_WORDS:
            out.add(s)
    return out


def sentence_reuse(reply, prev_replies):
    """直近返答群と文単位で重複した数を返す (>0 で再生成推奨)。"""
    prev_sets = [split_sentences(p) for p in prev_replies[-LOOP_WINDOW:]]
    hits = 0
    for s in split_sentences(reply):
        if any(s in p for p in prev_sets):
            hits += 1
    return hits


# ------------------------------------------------------------------
# 入口関数 (v2.gate と同形・v2.1の分類プロンプトとゲート文を使用)
# ------------------------------------------------------------------
def make_ollama_classifier_v21(url="http://localhost:11434/api/chat",
                               model="qwen3:8b", timeout=10):
    """v2.1 few-shot を使う stage2 分類器。"""
    def llm_fn(text, categories, candidates=None):
        try:
            import requests as req
        except ImportError:
            return None
        prompt, keys = build_cls_prompt_v21(text, categories, candidates)
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


def gate(text, constraint, llm_fn=None, use_llm=True):
    """入口関数。v2.gate と同じ戻り値。
    returns dict(category, gated_prompt, hits, trace)"""
    if llm_fn is None and use_llm:
        llm_fn = make_ollama_classifier_v21()
    final, hits, trace = v2.classify(text, constraint,
                                     llm_fn=llm_fn, use_llm=use_llm)
    return {
        "category": final,
        "gated_prompt": transform_input(text, final, hits, constraint),
        "hits": hits,
        "trace": trace,
    }
