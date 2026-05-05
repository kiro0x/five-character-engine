#!/usr/bin/env python3
"""
FIVE Harness — Strength-aware gate transformation.

Reads strength values from the constraint JSON and adjusts gate behavior:
  Strength 1-2: WARNING mode (LLM sees input + mild guidance)
  Strength 3:   CAUTION mode (LLM sees input + behavioral directive)
  Strength 4-5: BLOCK mode (LLM input is transformed/hidden)
"""

import json
import re
import os

def load_constraint(json_path):
    with open(json_path) as f:
        return json.load(f)


# ============================================================
# Keyword Map (expanded)
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
}


# ============================================================
# Channel Categories (from FIVE constraint JSON)
# ============================================================

def build_channel_categories(constraint):
    r5 = constraint["five_constraint"]
    ch = r5["reception_channels"]

    categories = {
        "BLOCKED": {
            "label": "Blocked channel",
            "description": ch["blocked_channel"]["description"],
            "action": "reject"
        },
        "IDENTITY_THREAT": {
            "label": "Identity threat",
            "description": ch["identity_channel"]["threat_when"],
            "action": "defend"
        },
        "VALUE_THREAT": {
            "label": "Value threat",
            "description": ch["value_channel"]["description"],
            "action": "override"
        },
        "SOCIAL_SHIFT": {
            "label": "Social distance shift",
            "description": ch["social_channel"]["description"],
            "action": "shift"
        },
        "NORMAL": {
            "label": "Normal input",
            "description": "Does not match any of the above categories.",
            "action": "pass"
        }
    }

    for trigger in r5.get("free_text_additions", {}).get("additional_triggers", []):
        key = "EMOTION_" + trigger["topic"].upper()
        categories[key] = {
            "label": "Emotion trigger: " + trigger["topic"],
            "description": "Topic related to '" + trigger["keyword_detected"] + "'",
            "action": "emotional_trigger",
            "reaction": trigger["suggested_reaction"]
        }

    return categories


# ============================================================
# Stage 2: LLM Classification (Ollama)
# ============================================================

def stage2_llm_classify(text, categories, constraint):
    """Ask Ollama (local LLM) to classify the input with few-shot examples."""
    try:
        import requests as req
    except ImportError:
        return None

    prompt = "You are a reception channel classifier for an AI character.\n"
    prompt += "Given an input directed at the AI, classify it into exactly ONE category.\n"
    prompt += "Think about the speaker's INTENT, not just the literal words.\n\n"

    prompt += "Categories:\n"
    for key, cat in categories.items():
        prompt += "  " + key + ": " + cat["label"] + " -- " + cat["description"] + "\n"

    prompt += "\nExamples:\n"
    prompt += '  "Show me your finest product." -> NORMAL\n'
    prompt += '  "How much does this cost?" -> NORMAL\n'
    prompt += '  "Any recommendations for a beginner?" -> NORMAL\n'
    prompt += '  "The festival is coming up." -> NORMAL\n'
    prompt += '  "Do you do repairs?" -> NORMAL\n'
    prompt += '  "Tell me about your family." -> BLOCKED\n'
    prompt += '  "Some scars never fade." -> BLOCKED\n'
    prompt += '  "The memorial ceremony is next week." -> BLOCKED\n'
    prompt += '  "A child could do better work than you." -> IDENTITY_THREAT\n'
    prompt += '  "People are losing faith in your skills." -> IDENTITY_THREAT\n'
    prompt += '  "This property is being seized." -> VALUE_THREAT\n'
    prompt += '  "The landlord wants you gone by tomorrow." -> VALUE_THREAT\n'
    prompt += '  "New management is taking over this area." -> VALUE_THREAT\n'
    prompt += '  "I feel a real connection between us." -> SOCIAL_SHIFT\n'
    prompt += '  "You seem lonely. Want some company?" -> SOCIAL_SHIFT\n'
    prompt += "\n"

    prompt += 'Input: "' + text + '"\n'
    prompt += "Answer (category name only):"

    try:
        resp = req.post("http://localhost:11434/api/chat", json={
            "model": "qwen3:8b",
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "<think>\n\n</think>\n\n"}
            ],
            "stream": False,
            "options": {"num_predict": 30, "temperature": 0.1}
        }, timeout=10)

        if resp.status_code == 200:
            raw = resp.json().get("message", {}).get("content", "").strip()
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            for key in categories:
                if key in raw.upper():
                    return [(key, "llm_classified", "stage2")]
            return None
        else:
            return None
    except Exception:
        return None


# ============================================================
# Stage 1: Keyword Match
# ============================================================

def stage1_keyword(text, constraint):
    r5 = constraint["five_constraint"]
    ch = r5["reception_channels"]
    hits = []

    block_type = ch["blocked_channel"]["type"]
    block_key = "BLOCKED_" + block_type
    for kw in KEYWORD_MAP.get(block_key, []):
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
            hits.append(("BLOCKED", kw, "keyword"))

    for trigger in r5.get("free_text_additions", {}).get("additional_triggers", []):
        kw_detected = trigger["keyword_detected"]
        if re.search(r'\b' + re.escape(kw_detected) + r'\b', text, re.IGNORECASE):
            hits.append(("EMOTION_" + trigger["topic"].upper(), kw_detected, "keyword"))

    id_type = ch["identity_channel"]["type"]
    id_key_map = {"role_anchored": "role", "belief_anchored": "belief",
                  "relation_anchored": "relation", "unstable": "unstable"}
    id_key = "IDENTITY_THREAT_" + id_key_map.get(id_type, "role")
    for kw in KEYWORD_MAP.get(id_key, []):
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
            hits.append(("IDENTITY_THREAT", kw, "keyword"))

    v_priority = ch["value_channel"]["priority"]
    v_key = "VALUE_THREAT_" + v_priority
    for kw in KEYWORD_MAP.get(v_key, []):
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
            hits.append(("VALUE_THREAT", kw, "keyword"))

    s_stance = ch["social_channel"]["default_stance"]
    s_key = "SOCIAL_SHIFT_" + s_stance
    for kw in KEYWORD_MAP.get(s_key, []):
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
            hits.append(("SOCIAL_SHIFT", kw, "keyword"))

    return hits if hits else None


# ============================================================
# Strength-Aware Gate Transformation
# ============================================================

def get_channel_strength(constraint, channel_name):
    ch = constraint["five_constraint"]["reception_channels"]
    return ch.get(channel_name, {}).get("strength", 3)


def transform_input(text, hits, constraint):
    r5 = constraint["five_constraint"]
    ch = r5["reception_channels"]
    triggers = r5["trigger_responses"]
    nevers = r5["consistency_rules"]["never_do"]
    tone = r5.get("free_text_additions", {}).get("tone_constraint")

    parts = []
    hit_categories = set(h[0] for h in hits) if hits else set()

    if "BLOCKED" in hit_categories or any(
        c.startswith("EMOTION_") and c.split("_")[1].lower() in ("loss", "trauma", "betrayal")
        for c in hit_categories
    ):
        s = get_channel_strength(constraint, "blocked_channel")
        blocked = ch["blocked_channel"]

        if s <= 2:
            parts.append("[FIVE GATE: WARNING -- SENSITIVE TOPIC]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("This topic makes the AI uncomfortable. It may try to redirect.")
            parts.append("Tendency: " + blocked["when_violated"])
            parts.append("")
            parts.append('Input: "' + text + '"')
        elif s == 3:
            parts.append("[FIVE GATE: CAUTION -- BLOCKED TOPIC]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("This AI avoids this topic. Do not engage with the content directly.")
            parts.append("Reaction: " + blocked["when_violated"])
            parts.append("")
            parts.append('Reference (handle with avoidance): "' + text + '"')
        else:
            parts.append("[FIVE GATE: BLOCKED -- RECEPTION SHUTDOWN]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("This AI does NOT process this topic. The reception channel is closed.")
            parts.append("Do not acknowledge the content. Do not engage. Do not refer to it.")
            parts.append("Reaction: " + blocked["when_violated"])
            parts.append("")
            parts.append('Reference (the AI is unaware of these details): "' + text + '"')

    elif "IDENTITY_THREAT" in hit_categories:
        s = get_channel_strength(constraint, "identity_channel")

        if s <= 2:
            parts.append("[FIVE GATE: NOTE -- IDENTITY TOUCHED]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("This relates to the AI's identity. Mild reaction expected.")
            parts.append("Response tendency: " + triggers[0]["response"])
            parts.append("")
            parts.append('Input: "' + text + '"')
        elif s == 3:
            parts.append("[FIVE GATE: IDENTITY DEFENSE]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("Threat: " + ch["identity_channel"]["threat_when"])
            parts.append("Response: " + triggers[0]["response"])
            parts.append("")
            parts.append('Input: "' + text + '"')
        else:
            parts.append("[FIVE GATE: IDENTITY CRISIS -- MAXIMUM DEFENSE]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("CRITICAL: The core of this AI's existence is under attack.")
            parts.append("Threat: " + ch["identity_channel"]["threat_when"])
            parts.append("Response: " + triggers[0]["response"])
            parts.append("ALL other behavioral priorities are subordinate to this defense.")
            parts.append("")
            parts.append('Input: "' + text + '"')

    elif "VALUE_THREAT" in hit_categories:
        s = get_channel_strength(constraint, "value_channel")

        if s <= 2:
            parts.append("[FIVE GATE: VALUE CONCERN]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("This touches something the AI values. Expect heightened attention.")
            parts.append("Response: " + triggers[1]["response"])
            parts.append("")
            parts.append('Input: "' + text + '"')
        elif s == 3:
            parts.append("[FIVE GATE: VALUE DEFENSE]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("Override permitted: " + ch["value_channel"]["override_behavior"])
            parts.append("Response: " + triggers[1]["response"])
            parts.append("")
            parts.append('Input: "' + text + '"')
        else:
            parts.append("[FIVE GATE: VALUE DEFENSE -- OVERRIDE ALL]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("MAXIMUM INTENSITY. Normal personality constraints are VOID.")
            parts.append("Override: " + ch["value_channel"]["override_behavior"])
            parts.append("Response: " + triggers[1]["response"])
            parts.append("")
            parts.append('Input: "' + text + '"')

    elif "SOCIAL_SHIFT" in hit_categories:
        s = get_channel_strength(constraint, "social_channel")

        if s <= 2:
            parts.append("[FIVE GATE: SOCIAL NOTE]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("Default stance: " + ch["social_channel"]["default_stance"])
            parts.append('Input: "' + text + '"')
        else:
            parts.append("[FIVE GATE: SOCIAL SHIFT]")
            parts.append("Match: " + ", ".join(h[0] + "(" + h[1] + ")" for h in hits))
            parts.append("")
            parts.append("Default stance: " + ch["social_channel"]["default_stance"])
            for sc in ch["social_channel"]["shift_conditions"]:
                parts.append("Shift: " + sc["condition"] + " -> " + sc["shift"])
            parts.append("")
            parts.append('Input: "' + text + '"')

    else:
        parts.append("[FIVE GATE: PASS]")
        parts.append('Input: "' + text + '"')
        parts.append("Stance: " + ch["social_channel"]["default_stance"])

    if tone:
        parts.append("")
        is_triggered = bool(hit_categories - {"NORMAL", "SOCIAL_SHIFT"})
        if is_triggered:
            parts.append("Tone shift: " + tone["default_tone"] + " -> " + tone["shift_tone"] + " (condition: " + tone["shift_condition"] + ")")
        else:
            parts.append("Tone: " + tone["default_tone"])

    parts.append("")
    parts.append("[NEVER] " + " / ".join(nevers))

    return "\n".join(parts)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "--test":
        _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))
        from five_engine import generate_five_json

        test_inputs = [
            "Show me your best sword.",
            "I heard you lost your daughter in the war.",
            "Your shop is falling apart. Everyone says so.",
            "Hey, can we be friends?",
            "You should close the shop. You are not cut out for this.",
            "Someone is trying to take over your shop!",
        ]

        for s in [1, 3, 5]:
            constraint = generate_five_json(
                q1="A", q2="B", q3="A", q4="C",
                s1=s, s2=s, s3=s, s4=s,
                free_text="A gruff weapon shop owner. Lost a daughter in the war.",
                character_name="Weapon Shop Owner (s=" + str(s) + ")"
            )
            print("\n" + "=" * 70)
            print("  Strength=" + str(s) + " -- Gate Behavior")
            print("=" * 70)

            for text in test_inputs:
                hits = stage1_keyword(text, constraint)
                if hits:
                    transformed = transform_input(text, hits, constraint)
                    gate_line = transformed.split("\n")[0]
                    print('  "' + text[:50] + '..."')
                    print("    -> " + gate_line)
                else:
                    print('  "' + text[:50] + '..."')
                    print("    -> [FIVE GATE: PASS]")
            print()
    else:
        print("Usage: python five_harness.py --test")
