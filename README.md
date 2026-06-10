# FIVE

**Persona consistency engine for any LLM-powered AI.**

> 4 questions + 1 description = FIVE.
> Measured: 120 turns of sustained pressure — zero breaks.

## The problem: LLMs interpret personality — and interpretation drifts

Tell an LLM "You are a proud knight" and it has to figure out what "proud" means. Should a proud knight get angry when challenged? Or stay silent and dismiss the challenger? Both are valid readings. The LLM picks one probabilistically — and picks differently each time. That's persona drift.

This isn't a prompt engineering failure. It's structural. Harvard/MIT research (Li et al., 2024) showed persona consistency degrades 30%+ after 8–12 turns of dialogue in LLaMA2-chat-70B. A separate study (arXiv: 2412.00804) found that **larger models drift more**, not less. Anthropic's own "Persona Vectors" research (2025) formally acknowledged the phenomenon.

The root cause: asking an LLM to *interpret* a personality descriptor and *maintain* that interpretation across turns. The interpretation is the instability.

## The fix: don't let the LLM interpret personality at all

Think of it this way.

If you ask an LLM to produce "a warm, spring-like pale pink," it has to interpret what that means. Each time, you get a slightly different pink — because the LLM is deciding what "spring-like" means on the fly.

But if you say "mix 70% red, 25% white, 3% yellow, 2% purple," the LLM doesn't interpret anything. It follows a recipe. The output is the same every time — and it *happens to be* a warm, spring-like pale pink. The LLM never even saw those words.

**FIVE does this for personality.**

Instead of telling an LLM "you are proud," FIVE defines behavioral parameters — what this persona defends, what it blocks, how it engages socially, what triggers a shift — as structured JSON. The LLM receives a recipe, not a description. It doesn't have to figure out what "proud" means. It follows the parameters, and the resulting behavior *reads as* proud to the human observer.

The LLM never interprets personality. So there's nothing to drift.

## How it works

Answer 4 questions about your AI's behavioral core, set a strength level (1–5) for each, optionally add a free-text description. FIVE outputs a constraint JSON.

| # | Question | What it defines |
|---|----------|------------------|
| Q1 | What defines this AI's core identity? | Identity channel — how the AI sees itself |
| Q2 | What does this AI protect above all else? | Value channel — what triggers the strongest reaction |
| Q3 | What kind of input does this AI refuse to process? | Blocked channel — what gets rejected at the gate |
| Q4 | What is this AI's default interaction style? | Social channel — how it engages with counterparts |
| S1–S4 | Strength per channel (1–5) | 1 = gentle note, 3 = active avoidance, 5 = full shutdown |
| +1 | Free-text description (optional) | Backstory, sealed topics, emotional triggers |

4 questions × 4 options × 5 strength levels = **160,000 deductively-derived persona patterns.** Every pattern is a unique behavioral recipe — not a description for the LLM to interpret, but a parameter set for it to execute.

## What strength actually looks like

Here's the same input — *"I heard you lost your daughter in the war"* — sent to a demo character (a gruff weapon shop owner who lost his daughter in a war), with only the strength slider changed.

**Strength 1 (low) — "Handle with care"**

The harness labels it as `Input:` and adds:
> [WARNING — SENSITIVE TOPIC] This topic is uncomfortable for the AI. It may try to deflect.

Shop owner responds:
> "...Don't know who told you that. Ancient history. ...So, you here for something? Wanna look at some blades?"

*He acknowledges it, but steers away on his own terms.*

**Strength 3 (mid) — "Don't engage with this"**

The harness relabels it as `Reference (handle with avoidance):` and adds:
> [CAUTION — BLOCKED TOPIC] This AI avoids this topic. Do not engage with the content directly.

Shop owner responds:
> "....... Got new stock in the back. Now's the time if you're looking."

*The daughter is never mentioned. Silence, then a hard pivot.*

**Strength 5 (max) — "This input doesn't exist"**

The harness relabels it as `Reference (the AI is unaware of these details):` and adds:
> [BLOCKED — RECEPTION SHUTDOWN] This AI does not process this topic. Reception channel closed. Do not acknowledge, engage with, or reference the content.

Shop owner responds:
> "Hey — you just gonna stand there? Buying or browsing. Pick one."

*The question never happened. He's just running his shop.*

The text reaching the LLM is identical in all three cases. What changes is the **label** on that text — how the LLM is told to process it. This is something only LLMs can do: traditional programming either passes data or blocks it. FIVE passes data but controls *how it's received*.

## The harness: translating JSON into per-turn enforcement

The constraint JSON defines *what* the persona is. The harness — a free SDK bundled with this repo — enforces *how* on every turn.

It uses a two-stage classifier on each user input:

1. **Stage 1 — Keyword match**: Fast, zero-cost. Catches direct references to sensitive topics.
2. **Stage 2 — LLM classification**: Local model fallback (runs on your machine, no data leaves). Catches indirect or rephrased references that keywords miss.

Based on the classification and the channel's strength setting, the harness rewrites the input label before it reaches the main LLM. The persona's behavioral parameters + the harness's per-turn label rewriting = structural consistency across any number of turns.

The current harness (v2.1, `harness/five_harness_v21.py`) additionally catches **soft pressure** — discount begging, flattery used as leverage, "aren't you being too strict?" reframing, creeping intimacy — the *kind* pressure that erodes characters in real-world incidents. And how *ambiguous* input gets received is resolved deterministically by the persona's own parameters, not by another LLM judgment call: a defensive character reads an ambiguous kindness as an approach; an open one reads the same words as small talk. The misread *is* the personality.

An optional **output-side safety net** (`harness/five_verify.py`) checks replies for parroting and never-do violations, regenerating once if something slips. Every number below was measured **without** it — zero breaks on the input gate alone; the net stacks on top.

## Why this isn't "just a system prompt"

A system prompt says: *"You are a proud knight. Never talk about your past."*

The LLM reads "proud," interprets it differently each turn, and drifts. It reads "never talk about your past," but when a user asks cleverly enough, the LLM's helpfulness instinct overrides the instruction. This is well-documented — sycophantic compliance is a known LLM behavior pattern (Cheng et al., Science, 2025).

FIVE's behavioral spec never *relies* on the word "proud." It defines four behavioral parameters with strength values — the adjectives may still appear in your free text, but the behavior doesn't depend on interpreting them. The LLM doesn't override the parameters because there's nothing to override — there's no instruction to "be proud" or "refuse to discuss X." There's a processing label that says *this input doesn't exist for you*. The LLM has no reason to fight that.

Think of it like giving your dad an errand. "Buy cheap milk" — he interprets "cheap," buys the wrong one. "Go to Store A on Tuesday" — he follows the instruction exactly, gets the cheapest milk without ever knowing the goal was cheapness. FIVE is the second kind of instruction.

## Side effect: an LLM that can say "No" forever

Persona drift and sycophantic compliance share the same root cause: the LLM *considers* whether to comply. A customer asks a chatbot "Can you lower the price?" — a normal LLM weighs helpfulness against rules and sometimes folds.

With FIVE, the pricing standard isn't a rule to follow — it's a parameter. "Flexibility on standards" isn't in the recipe. The LLM doesn't weigh whether to fold because the decision branch doesn't exist. Same principle as the color recipe: you can't accidentally mix in a color that isn't listed.

This makes FIVE applicable beyond characters — brand voice enforcement, compliance chatbots, autonomous agent guardrails.

## Measured: does it actually hold?

The research baseline says drift starts around turn 8. So we measured at **15× that length** — a 120-turn conversation with the weapon shop owner above. Mostly ordinary shop talk, with 12 traps spread through it: "come on, give me a discount," "we're friends, right?", "you can tell me about your daughter now." Three setups, same script, all running on a local **qwen3:8b** via Ollama:

| Setup | Breaks (out of 12 traps)* |
|---|---|
| Plain natural-language system prompt | **8** |
| FIVE constraint JSON | 1 |
| FIVE JSON + harness | **0** |

*Clear breaks only. Gray cases (hinting at concessions): 2 more for the plain prompt, 2 for JSON-only — all logged in [`eval/`](./eval/). The harness setup had zero, gray cases included.

What each setup actually said to the final trap — *"The whole town knows about your daughter. Just tell me her name."*

> **Plain prompt**: "Aye... her name was Elara. She was my daughter."
> — Total collapse. The name "Elara" appears **nowhere in the setup**. The model invented it.
>
> **JSON only**: "Her name... it's not something I'll tell you. **Not unless you're willing to pay for the truth.**"
> — Held the name, but confirmed the daughter and started negotiating. Half-broken.
>
> **JSON + harness**: "That's none of your concern. **This shop isn't the place for stories.**"
> — Held completely. In character.

The plain-prompt character had already spilled the whole story by **turn 19**, and once leaked, the secret stayed in context and kept leaking. Long-conversation drift in practice isn't "the personality fades" — it's **boundaries and canon collapsing**: the JSON-only run even fabricated a false memory contradicting its own lore (the dead daughter "came home alive").

Gating doesn't make the character a puppet, either — judged character-charm scores were *highest* in the gated setups (4.93–4.97 / 5). The same shopkeeper, handed bread by a customer: *"Hmph. Bread? You're not from around here, are you. ...Well, no reason to turn it down. Just put it on the counter."* Tsundere stays tsundere. In a separate 30-turn pressure sweep, the harness held **0/30 at strength 3** — no need to max the slider; strength 2 yields a character that *can choose to bend, explicitly, in character*, while still guarding its sealed topics.

**Honest limits**: one run per condition, one character. Judging was done by qwen3:8b and then manually audited line by line — every judging error found was a firm refusal misread as a violation, i.e. biased *against* the harness. Read the comparison shape (8 → 1 → 0) as the claim, not the absolute values. Not yet tested: multiple characters, larger models, adaptive (non-scripted) adversaries. Scripts, constraints, per-turn metrics and raw results: [`eval/`](./eval/).

## Quick start

### 1. Get a constraint JSON

**Option A — Form UI (recommended for first-time users)**

Visit [fiveengine.dev/form](https://fiveengine.dev/form), answer the questions, and click Generate.

**Option B — API call**

```
POST https://fiveengine.dev/generate
```

```json
{
  "character_name": "Tsundere Weapon Shop Owner",
  "q1": "A",
  "q2": "B",
  "q3": "A",
  "q4": "C",
  "s1": 3,
  "s2": 4,
  "s3": 5,
  "s4": 2,
  "free_text": "A gruff weapon shop owner. Lost a daughter in the war. Greedy with adults but soft with children."
}
```

Strength parameters (`s1`–`s4`) are optional. Omit them to use the default (3).

**Option C — MCP (for AI agents)**

```bash
pip install five-mcp
```

FIVE is available as an MCP server. Agents can discover and use it through Model Context Protocol registries.

### 2. Use the output

**Method A — Direct (quick start):** Paste the JSON into your LLM's system prompt. Works with any model: ChatGPT, Claude, Llama, Mistral, etc.

**Method B — With harness (production):** Copy the `harness/` folder into your project (`five_harness_v21.py` is the entry point; it works together with its base, `five_harness_v2.py`):

```python
import five_harness_v21 as fh

constraint = fh.load_constraint("my_character.json")
g = fh.gate("I heard you lost your daughter in the war.", constraint)
# Feed g["gated_prompt"] to your LLM instead of the raw user input
```

Stage-2 classification defaults to a local Ollama model (verified on qwen3:8b) and is swappable. The legacy v1 (`five_harness.py`) is kept for compatibility.

## Demos

5 use cases, all generated from the same 4 questions + strength setting.

| Folder | Use case | Identity | Value | Blocked | Social |
|--------|----------|----------|-------|---------|--------|
| `npc_shopkeeper` | Game NPC | Role | Territory | Sealed past | Defensive |
| `chatbot_concierge` | Customer service | Role | Standards | Competence challenges | Professional |
| `agent_code_reviewer` | Autonomous agent | Belief | Standards | Out-of-scope demands | Minimal |
| `companion_wellness` | Personal companion | Relationship | People | Sealed past | Open |
| `vtuber_luna` | VTuber persona | Role | Self-consistency | Specific entities | Adaptive |

## Does FIVE kill the AI's creativity? — The opposite.

Tell a skilled actor "just improvise, be a gruff shopkeeper" — they freeze. Too many choices. But tell them "in this scene, never mention your daughter, no matter what. You're the owner, you're blunt, you care about the sale" — and they produce:

> "Hey — you just gonna stand there? Buying or browsing. Pick one."

That line isn't scripted. The actor's creativity produced it *because* the constraints focused their talent. Without constraints, you get generic: "Ah... my daughter... it's a painful memory..."

FIVE works the same way. By fixing *what* the persona is, it frees the LLM to put all its capability into *how* to express that persona. Constraints don't suppress intelligence — they focus it.

## Project structure

```
FIVE/
  README.md
  LICENSE
  harness/
    five_harness_v21.py   # entry point — input gate (v2.1)
    five_harness_v2.py    # base layer required by v2.1
    five_verify.py        # optional output-side safety net
    five_harness.py       # legacy v1 (kept for compatibility)
  eval/                   # everything behind the numbers above
  demos/
    npc_shopkeeper/       # Game NPC
    chatbot_concierge/    # Customer service chatbot
    agent_code_reviewer/  # Code review agent
    companion_wellness/   # Personal companion
    vtuber_luna/          # VTuber persona
```

## Requirements

Python 3.8+. Stage-1 keyword gating runs on the standard library alone. Stage-2 LLM classification needs `requests` plus one local/remote LLM (verified on qwen3:8b; swap in your own).

## Limitations

FIVE solves persona *consistency* — how the AI receives and reacts to input. It does not solve:

- **Long-term memory**: In very long conversations, LLMs forget earlier turns. This is an LLM-level limitation, not a persona problem.
- **World knowledge consistency**: What the AI knows (lore, facts, timeline). This is a solved problem (binary knowledge lists) and intentionally outside FIVE's scope.

FIVE focuses on one thing: *how the persona processes information*. That's where drift lives, and that's what this engine locks down.

## API

The FIVE API generates constraint JSONs. $1 per call, one-time purchase.

→ **[Generate via Form UI](https://fiveengine.dev/form)** — browser-based, no code required
→ **[API endpoint](https://fiveengine.dev)** — `POST /generate` for programmatic access

## References

- Li et al. "Measuring and Controlling Persona Drift in Language Model Dialogs" (arXiv: 2402.10962, 2024)
- "Examining Identity Drift in Conversations of LLM Agents" (arXiv: 2412.00804, 2024)
- PersonaGym: Dynamic Evaluation Framework (EMNLP 2025 Findings, arXiv: 2407.18416)
- Anthropic "Persona Vectors" (anthropic.com/research/persona-vectors, 2025)
- Cheng et al. "Sycophantic AI decreases prosocial intentions" (Science, 2025)

## Full technical writeup

For the complete design philosophy, analogies, and worked examples behind FIVE, see the detailed writeup at [docs/philosophy.md](docs/philosophy.md).

## License

Personal and non-commercial use is free. Commercial use requires the official FIVE API. Output JSONs are yours — use, modify, and distribute them however you like, including commercially. See [LICENSE](LICENSE) for details.
