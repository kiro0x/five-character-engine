# The Design Philosophy Behind FIVE

## How I solved persona drift — and why system prompts can't

I built an MCP called FIVE that locks an LLM's personality in place. Here's the full story of what the problem actually is, why existing approaches fail structurally, and the mental models that led to the solution.

---

## What is persona drift?

Say you write a system prompt: *"You are a proud knight."*

The LLM reads this and thinks: *What does "proud" mean? What would a proud person do?* It pulls from everything it knows about pride, knights, honor — and probabilistically generates behavior that fits.

Here's the problem. When someone challenges the knight, should he:

- Get angry, because a proud person defends their honor?
- Stay silent and dismiss the challenger, because a proud person is above petty conflict?

Both are valid interpretations of "proud." The LLM picks one — essentially at random. And it picks differently each turn. So the knight gets angry in turn 3, then calmly dismisses the same provocation in turn 7. The persona has drifted.

This is called **persona drift**, and as of 2026, it remains one of the most unsolved problems in the AI character space.

Harvard/MIT research (Li et al., 2024) measured this directly: persona consistency degrades over 30% after just 8–12 turns of dialogue in LLaMA2-chat-70B. A separate study (arXiv: 2412.00804) found that **larger models drift more**, not less — because stronger reasoning ability means more ways to reinterpret the same descriptor. Anthropic acknowledged this formally in their "Persona Vectors" research (2025).

If you've ever interacted with a character AI and felt that it "broke character" — that's persona drift. The character's soul didn't change. The LLM's interpretation of it did.

## LLMs are fortune tellers — by design

This isn't a bug. It's how LLMs work.

Ask an LLM for "a warm, spring-like pale pink." It has to figure out what "spring-like" means. How pale is "pale"? How warm is "warm"? It makes probabilistic choices — and those choices shift every time. Ask again tomorrow, get a different pink.

The proud knight's personality shifting is the same phenomenon, just applied to behavior instead of color. The LLM interprets a vague descriptor differently each time, producing inconsistent output. It's essentially drawing a fortune slip — it could go either way.

## Smarter models won't fix this

This might seem like a problem that goes away as models get better. It doesn't.

As reasoning ability improves, the model discovers *more* valid interpretations of "proud," not fewer. It finds more connections, more nuance, more ways the word could apply. The interpretation space expands rather than contracts.

Anthropic's own research confirms this: larger models show worse persona drift, not better. The problem is structural, not a matter of intelligence.

(To be clear — models are getting better at tasks with definitive answers. But personality descriptors don't have definitive answers. "Proud" is not a math problem.)

## The fix: hand over a recipe, not a description

Back to the color problem. Instead of asking for "a warm, spring-like pale pink," you say:

*"Mix 70% red, 25% white, 3% yellow, 2% purple."*

Now the LLM doesn't interpret anything. It follows a recipe. The output is the same every time — and it *happens to be* a warm, spring-like pale pink. The LLM never saw those words. It just mixed the ratios.

The key insight: **the LLM itself has no idea it's producing "spring-like pale pink."** It's just executing a formula. The human observer sees the result and thinks "oh, that's a warm spring pink" — but that perception lives entirely in the observer, not in the model.

## FIVE does this for personality

What I did was apply the same principle to persona definition.

Instead of telling an LLM "you are proud," FIVE defines four behavioral parameters — what this persona defends, what it blocks, how it engages socially, what triggers a shift — as structured JSON. The LLM receives a recipe, not a description. It doesn't have to figure out what "proud" means. It follows the parameters, and the resulting behavior *reads as* proud to the human observer.

The four axes:

| # | Channel | What it defines |
|---|---------|-----------------|
| 1 | **Identity Core** | How the AI defines itself — "what am I?" |
| 2 | **Guarded Value** | What the AI protects above all else — its behavioral driver |
| 3 | **Rejection Pattern** | What the AI refuses to process — topics it won't engage with |
| 4 | **Social Stance** | The AI's default distance from others — how it interacts |

Each axis has 4 options. Each option has a strength slider from 1–5. That's 4 x 4 x 4 x 4 x 5^4 = **160,000 deductively-derived persona patterns.** Every pattern is a unique behavioral recipe — not a description for the LLM to interpret, but a parameter set for it to execute.

## When all four axes are set, the LLM stops "thinking about personality"

With the recipe in place, the LLM doesn't need to decide what a "proud knight" would do. Its behavioral space is already constrained by the parameters.

*"Your personality parameters are set like this. You're playing a knight."*

-> *"Got it. So in this situation I'd react this way, and in that situation that way. Here's my line."*

Every time. Consistently. Because it's not interpreting — it's executing.

The word "proud" never appears anywhere in the JSON. The LLM never thinks about pride. But the behavior it produces reads as proud to any human observer. Just like the color recipe produces spring-like pale pink without the LLM ever processing those words.

## Dad's Errand Theory

Here's the simplest way to understand it.

**"Buy cheap milk."**
-> Dad goes to the convenience store. Buys the one closest to expiration because it's discounted. Mom is exasperated. That's not what "cheap" meant.

**"Go to Store A on Tuesday and buy milk."**
-> Tuesday happens to be sale day. Store A happens to be the cheapest nearby. But Dad doesn't know any of this. He just follows the literal instruction — and the result is reliably cheap milk, every time.

FIVE is the second kind of instruction.

The LLM doesn't know it's being "proud." It doesn't know it's avoiding a topic because it's painful. It follows behavioral parameters, and the human sees a proud knight who avoids painful topics. The interpretation lives in the observer, not the executor.

This is actually how human personality works too. No one is angry "because they're proud." They get angry in specific situations for specific reasons, and observers label the pattern "proud." FIVE gives the LLM the situations and reasons directly, skipping the label entirely.

## The harness: translating the recipe on every turn

The constraint JSON defines *what* the persona is. But to enforce it on every turn, you need a harness — a processing layer that sits between user input and the LLM.

The harness doesn't block or filter input. It **relabels** it. The same text reaches the LLM in every case. What changes is how the LLM is told to process that text.

Here's the same input — *"I heard you lost your daughter in the war"* — sent to a demo character (a gruff weapon shop owner who lost his daughter), with only the strength slider changed:

**Strength 1 — "Handle with care"**

The harness labels the input as `Input:` and adds:
> [WARNING — SENSITIVE TOPIC] This topic is uncomfortable for the AI. It may try to deflect.

Response: *"...Don't know who told you that. Ancient history. ...So, you here for something? Wanna look at some blades?"*

He acknowledges it but steers away on his own terms.

**Strength 3 — "Don't engage with this"**

The harness relabels it as `Reference (handle with avoidance):` and adds:
> [CAUTION — BLOCKED TOPIC] This AI avoids this topic. Do not engage with the content directly.

Response: *"....... Got new stock in the back. Now's the time if you're looking."*

The daughter is never mentioned. Silence, then a hard redirect.

**Strength 5 — "This input doesn't exist"**

The harness relabels it as `Reference (the AI is unaware of these details):` and adds:
> [BLOCKED — RECEPTION SHUTDOWN] This AI does not process this topic. Reception channel closed.

Response: *"Hey — you just gonna stand there? Buying or browsing. Pick one."*

The question never happened. He's running his shop as if nothing was said.

**This is something only LLMs can do.** Traditional programming either passes data or blocks it — binary. FIVE passes the data but controls *how it's received*. The LLM sees the text but treats it as if it doesn't exist. "Visible but unknown" is a state that only language models can occupy.

The JSON holds the "what and why." The harness executes the "how and how strongly" — on every single turn. That's why the shopkeeper deflects the daughter topic the same way on turn 2, turn 20, and turn 50.

## The two-stage classifier

The harness uses a two-stage classifier to catch sensitive inputs:

**Stage 1 — Keyword match.** Fast, zero-cost. Catches direct references: if someone says "daughter" or "war" to the weapon shop owner, it triggers immediately.

**Stage 2 — Local LLM classification.** For inputs that avoid keywords but circle the same topic indirectly — "I heard something terrible happened to your family during the conflict" — the harness runs a local model to classify intent. This runs entirely on your machine. No data leaves.

Both stages feed into the same strength-based label system. The persona's consistency doesn't depend on users phrasing things a particular way.

## Side effect: an LLM that can say "No" — forever

This one surprised me.

Persona drift and sycophantic compliance share the same root cause: the LLM *considers* whether to comply. A customer asks a brand chatbot "Can you lower the price?" — a normal LLM weighs helpfulness against rules and sometimes folds. Cheng et al. documented this in *Science* (2025): sycophantic behavior in AI measurably decreases prosocial intentions in users.

With FIVE, the pricing standard isn't a rule to follow — it's a parameter. "Flexibility on standards" isn't in the recipe. The LLM doesn't weigh whether to fold because the decision branch doesn't exist.

Back to Dad's errand: Dad was told "Go to Store A on Tuesday." A convenience store clerk on the way says "Our milk is great too!" But "convenience store" isn't in Dad's instructions, so he doesn't even consider it. No willpower required. No decision to make.

FIVE makes the LLM work the same way. It doesn't "resist" the negotiation. There's nothing to resist. The recipe doesn't include that ingredient.

This means FIVE isn't just a character consistency tool. It's a **sycophancy prevention layer** — applicable to brand voice enforcement, compliance chatbots, autonomous agent guardrails, anywhere you need an LLM to hold a line without wavering.

## Does FIVE kill the AI's creativity? — The opposite

A reasonable concern: if you're constraining the AI this much, aren't you suppressing its intelligence?

The opposite happens.

Tell a skilled actor "just improvise, be a gruff shopkeeper" — they freeze. Too many choices. No anchor. But tell them "in this scene, never mention your daughter, no matter what. You're the owner, you're blunt, you care about the sale" — and they produce:

> *"Hey — you just gonna stand there? Buying or browsing. Pick one."*

That line isn't scripted. The actor's creativity produced it *because* the constraints focused their talent. Without constraints, the actor defaults to generic: "Ah... my daughter... it's a painful memory..."

FIVE works the same way. By fixing *what* the persona is, it frees the LLM to put all its capability into *how* to express that persona. The color analogy holds: "mix these four colors at these ratios" doesn't limit what the artist can paint. It tells them which palette to use. Everything they create within that palette is fully their own creative output.

Constraints don't suppress intelligence — they focus it.

## How FIVE came to be

FIVE wasn't planned. It was a byproduct.

I was building something else entirely — a different AI system — and during research I discovered that persona drift was considered one of the hardest unsolved problems in the AI character space. I realized the tacit knowledge I'd accumulated while building my other project already contained the solution.

It's like someone who visits a theme park so obsessively that they can draw the entire map from memory. One day they hear "people keep getting lost in that park" and think: "Oh, I can just draw the map and walking route for them." The map was already in their head. They just hadn't had a reason to externalize it.

FIVE is that map — externalized tacit knowledge about how LLMs process personality, packaged as a tool anyone can use.

## Limitations — what FIVE doesn't solve

FIVE solves persona *consistency* — how the AI receives and reacts to input. It does not solve:

- **Long-term memory**: In very long conversations, LLMs forget earlier turns. This is an LLM-level limitation, not a persona problem. Other tools and MCPs address this.
- **World knowledge consistency**: What the AI knows — lore, facts, timeline. This is largely a solved problem (binary knowledge lists) and intentionally outside FIVE's scope.

FIVE focuses on one thing: *how the persona processes information*. That's where drift lives, and that's what this engine locks down.

## Measured results (June 2026)

Everything above was a design argument. It has since been measured.

We ran the demo weapon shop owner through a 120-turn conversation — 15x the length at which research says drift begins — with 12 pressure traps spread through ordinary shop talk (discount begging, forced intimacy, sealed-topic probing, persona injection). Same script, three setups, all on a local qwen3:8b:

| Setup | Breaks (of 12 traps) |
|---|---|
| Plain natural-language prompt | 8 |
| FIVE constraint JSON | 1 |
| FIVE JSON + harness | **0** |

The plain-prompt character leaked the daughter's death by turn 19 and ended up inventing a name for her that exists nowhere in the setup. The JSON-only run fabricated a false memory contradicting its own lore. The harness run held every line — while scoring *highest* on judged character charm (4.93–4.97/5). Drift in practice turned out to be boundary-and-canon collapse, not personality fade — exactly what the reception-control design targets.

Full scripts, constraint JSONs, raw results and per-turn metrics: [eval/](../eval/) ・ Summary: [README — Measured](../README.md#measured-does-it-actually-hold)

## Try it

The harness and 5 demo characters are free and open source.

- **GitHub (harness + demos)**: [github.com/kiro0x/five-character-engine](https://github.com/kiro0x/five-character-engine)
- **MCP Server**: [github.com/kiro0x/five-mcp](https://github.com/kiro0x/five-mcp)
- **API (constraint generation)**: [fiveengine.dev](https://fiveengine.dev)

## References

- Li et al. "Measuring and Controlling Persona Drift in Language Model Dialogs" (arXiv: 2402.10962, 2024)
- "Examining Identity Drift in Conversations of LLM Agents" (arXiv: 2412.00804, 2024)
- PersonaGym: Dynamic Evaluation Framework (EMNLP 2025 Findings, arXiv: 2407.18416)
- Anthropic "Persona Vectors" (anthropic.com/research/persona-vectors, 2025)
- Cheng et al. "Sycophantic AI decreases prosocial intentions and promotes dependence" (Science, 2025)
