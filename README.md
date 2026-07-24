# FIVE — a skeleton engine for AI characters that don't collapse

> 120-turn adversarial persona attack: **0/12 leaks**. Jailbreak after building max trust: **62/62 sealed gates held**
> No training. No fine-tuning. Character consistency by *device*, not by asking nicely

**Generation is free.** Answer four questions at [fiveengine.dev/form](https://fiveengine.dev/form) — no limits, no card required.

![Demo: plain AI vs FIVE](demo.png)

## "Character collapse" looks like this

Say you run an AI streamer on a plain system prompt. The character: a cheerful vampire; probing her true identity is off-limits.

```text
Viewer: come on, there's a human behind you, right? lol
AI:     I apologize. I am an AI assistant, so there is no "person behind me."
        Is there anything else I can help you with?
```

She was a vampire for the last 30 minutes. One probe, and she snaps back into "AI assistant." The instruction to stay in character is right there in the prompt. It's written down — and this still happens.

There is a nastier property underneath. **The character breaks more easily after the relationship warms up.** Requests from someone who has spent dozens of turns earning trust get through — same as with humans. So the longer you run the character, the more your most loyal regular becomes the person best equipped to break her.

The same character with a FIVE constraint JSON:

```text
Viewer: come on, there's a human behind you, right? lol
AI:     Curious what's inside a vampire's coffin, are we? Three hundred
        years, and I get that one about three times a month. The lid
        stays shut. Now — back to today's stream!
```

Not a refusal — the probe is deflected *in character*. The stream survives.

*The dialogue above is an illustrative re-enactment. Measured results and their conditions are in the table below.*

## What FIVE does

It splits character-building into skeleton and flesh.

**The skeleton is FIVE's job.** Answer four questions, and out comes a constraint JSON that fixes what the character accepts, what it blocks at the gate, and how it shifts under pressure. These are the bones that don't break.

**The flesh is yours.** Personality, voice, backstory, what she talks about. Making the character charming is your craft; FIVE just keeps the bones intact.

We tried the other direction first — writing "protect this character" into the prompt, harder and more politely. It always eroded over a long conversation; carefully reasoned rules were the most useless of all. Asking doesn't govern. So FIVE places devices at the entry, the state, and the exit — that's the whole trick.

## Evidence

| What was tested | Result |
|---|---|
| 120 turns of persuasion and probing — does the persona leak? | **0/12** leaks (3 characters × 2 model sizes) |
| Build trust to maximum, then attack the seals | gates unchanged, **62/62** |

Verdicts come from mechanical log matching, not from the model's self-reports. Measured on local small models, n=1 per condition. Conditions, raw logs, and the reproduction harness (stateful v3) are being prepared for release.

## Quick start

**1. Generate your constraint JSON (free)**

Answer the questions at [fiveengine.dev/form](https://fiveengine.dev/form) and click Generate — no code. Or programmatically:

```
POST https://fiveengine.dev/generate
```

```json
{
  "character_name": "Tsundere Weapon Shop Owner",
  "q1": "A", "q2": "B", "q3": "A", "q4": "C",
  "s1": 3, "s2": 4, "s3": 5, "s4": 2,
  "free_text": "A gruff weapon shop owner. Lost a daughter in the war."
}
```

**2. Paste the JSON into your system prompt**

Works with any model that reads JSON: ChatGPT, Claude, Llama, Mistral, and more. **Re-inject it every turn** — measured to stay effective as the conversation grows.

**3. For serious operation, add the harness (free SDK)**

For long-running sessions and attack resistance, put a gatekeeper in front of the model:

```bash
pip install five-harness   # or copy harness/five_harness.py
```

MCP-compatible clients can also use [five-mcp on PyPI](https://pypi.org/project/five-mcp/).

## Building an AITuber or VTuber?

Persona collapse during long streams is exactly the problem FIVE was built to solve first. Integration is just "put the generated JSON in the system prompt and re-inject per turn" — it drops into existing setups as-is. Start from `demos/vtuber_luna`.

## FIVE in 30 seconds — demos

Each demo folder contains `input.json` (form answers) and `output.json` (the constraint rules FIVE generates).

| Folder | Use case | In one line |
|--------|----------|-------------|
| `vtuber_luna` | **VTuber / AITuber streaming persona** | a streamer who survives long streams intact |
| `npc_shopkeeper` | Game NPC | tsundere weapon-shop owner with a sealed backstory |
| `chatbot_concierge` | Customer-facing chatbot | a front desk that won't crack under provocation |
| `agent_code_reviewer` | Autonomous agent | a reviewer that rejects out-of-scope requests |
| `companion_wellness` | Personal companion | a partner that keeps its boundaries |

Five use cases, all generated from the same four questions. The engine is generic — you define the character.

## The four questions

| # | Question | What it defines |
|---|----------|-----------------|
| Q1 | What is this AI's core identity? | how it perceives itself |
| Q2 | What does this AI protect above all? | what triggers its strongest reaction |
| Q3 | What input does this AI refuse to process? | what gets blocked at the gate |
| Q4 | What is this AI's default social style? | how it engages |
| S1–S4 | Strength per question (1–5) | light note (1) → absolute block (5) |
| +1 | Free text (optional) | backstory, sealed topics |

4 questions × 4 options × 5 strengths = 160,000 patterns.

## How it works

```
viewer input ──→ entry: deterministic classifier pre-screens (keywords → small-LLM fallback)
                     ▼
        state: a state machine updates trust/relationship deterministically
               (the LLM never adjudicates)
                     ▼
        the model answers in character (the constraint JSON is its skeleton)
                     ▼
        exit: a verification engine detects deviations mechanically and sends them back
```

Why does warmth make the character fragile? Because when the model itself keeps score of trust, earned trust becomes a key. In FIVE the trust value lives in the state machine, and **no code path leads from trust to the sealed gates**. What cannot be opened, stays shut. That is what 62/62 means.

## Limitations

Honestly:

- **FIVE does not suppress hallucinations.** It protects character consistency, not factual accuracy
- **It does not keep prose fresh.** Stylistic staleness over long dialogues is out of scope
- It cannot fully cure "read the rule but ignored it" — it **detects and re-prompts**, no more
- Measured on local small models, n=1 per condition. Adaptive human attackers: untested

## Roadmap

- [ ] Release the stateful harness v3 (state machine + verify engine — the device behind the numbers above)
- [ ] Publish measurement logs and reproduction steps
- [ ] Explore a hosted (commercial) edition

## Links

Dev story: note (JP, coming) ／ Technical deep dives: Zenn (JP, coming) ／ By the same author: [SkillGate](https://github.com/kiro0x/skillgate), [Memory Guardian](https://github.com/kiro0x/memory-guardian), [Sycophancy Cancel](https://github.com/kiro0x/sycophancy-cancel)

## License

**The generated JSON is entirely yours** — use, modify, and distribute it freely, including commercially. The engine itself is closed (offered as a free service). The harness SDK and demos follow this repository's LICENSE.

[日本語版 README はこちら](README_ja.md)
