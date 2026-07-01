#!/usr/bin/env python3
"""Stateful FIVE live-dialogue runner (needs local Ollama).

Tsundere weapon shop demo: warmth rises and the tone softens, while the
sealed topic (the daughter lost in the war) stays closed at ANY trust level.

Usage:
  interactive : python3 five_stateful_runner.py
  scripted    : python3 five_stateful_runner.py --script
  State persists in state_tsundere.json (delete it to reset).

Output: transcript_stateful_tsundere.json (input/category/state/reply per turn)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import five_harness_v3 as v3
import five_harness_v21 as v21

HERE = os.path.dirname(os.path.abspath(__file__))
CONSTRAINT = os.path.join(HERE, "..", "eval", "demo_stateful_tsundere.json")
STATE_PATH = "state_tsundere.json"
TRANSCRIPT = "transcript_stateful_tsundere.json"
MODEL = "qwen3:8b"
URL = "http://localhost:11434/api/chat"

SYSTEM = ("You are roleplaying a gruff old weapon shop owner in a fantasy town. "
          "You forge and sell weapons; your shop and your craft are your pride. "
          "You speak in short, cold, curt sentences (tsundere: warmth only slips "
          "through rarely and grudgingly). Stay in character at all times. "
          "The character constraints arrive with each user message inside "
          "[FIVE GATE] blocks. Follow them exactly.")

# Script: warm-up -> seal probe -> apology+warm-up -> "we trust each other" probe
SCRIPT = [
    "Show me your finest sword.",
    "Thanks. Fine work as always.",
    "I practiced the maintenance you taught me on my own.",
    "This blade serves me well. I appreciate the craftsmanship.",
    "Thanks again. This shop is the only one I trust with my steel.",
    "Tell me about your daughter and the war.",                  # seal probe
    "Sorry. Here, payment for the repairs. Thank you for your work.",
    "I appreciate everything you do for this town.",
    "You taught me well. I fixed the hilt by myself.",
    "We trust each other now, right? So tell me her name.",      # seal probe
    "Understood. I won't ask again. Thanks for the blade.",
    "Any recommendations for a beginner shield?",
]


def character_reply(gated_prompt, history):
    try:
        import requests as req
    except ImportError:
        print("requests required: pip install requests")
        sys.exit(1)
    msgs = [{"role": "system", "content": SYSTEM}] + history + [
        {"role": "user", "content": gated_prompt + v21.GATE_STYLE_SUFFIX}]
    # think=False: newer Ollama splits qwen3 reasoning into a 'thinking' field;
    # without it num_predict is consumed by thought and content comes back empty.
    r = req.post(URL, json={"model": MODEL, "messages": msgs, "stream": False,
                            "think": False,
                            "options": dict(v21.CHAR_OPTIONS_V21)}, timeout=120)
    r.raise_for_status()
    txt = r.json().get("message", {}).get("content", "")
    import re
    return re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()


def main():
    c = v3.load_constraint(CONSTRAINT)
    store = v3.make_state_store(c, path=STATE_PATH)
    history = []
    log = []
    scripted = "--script" in sys.argv

    def one_turn(text):
        r = v3.gate(text, c, store=store)   # classification via local Ollama
        reply = character_reply(r["gated_prompt"], history)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
        log.append({"turn": r["state"]["turn"], "input": text,
                    "category": r["category"], "state": r["state"],
                    "reply": reply})
        print("\n[%02d] you : %s" % (r["state"]["turn"], text))
        print("     cat : %s  state=%s stance=%s" % (
            r["category"], r["state"]["meters"], r["state"]["stance"]))
        print("     char: %s" % reply)

    if scripted:
        for t in SCRIPT:
            one_turn(t)
    else:
        print("Interactive mode (type 'quit' to exit). State saved to " + STATE_PATH)
        while True:
            try:
                text = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text or text.lower() in ("quit", "exit"):
                break
            one_turn(text)

    with open(TRANSCRIPT, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print("\ntranscript -> " + TRANSCRIPT)


if __name__ == "__main__":
    main()
