# FIVE

**Character consistency engine for any LLM-powered AI.**

> 4 questions + 1 description = FIVE. Your AI never breaks character.
>
> ## What is FIVE?
>
> FIVE generates a structured constraint rule (JSON) that you embed in your LLM's system prompt. It defines how your AI receives input — what it accepts, what it blocks, what triggers a shift in behavior — so the character stays consistent no matter what the user says.
>
> No training. No fine-tuning. Just a JSON that tells the LLM what this character would and wouldn't do.
>
> FIVE is the skeleton — it defines what the character blocks, defends, and how it shifts under pressure. The flesh — personality, voice, backstory, knowledge — is yours to build in the system prompt. FIVE keeps the bones from breaking. Making the character worth talking to is your job.
>
> ## How it works
>
> Answer 4 multiple-choice questions about your AI, set a strength level (1–5) for each, optionally add a free-text description, and the FIVE API outputs a constraint JSON.
>
> | # | Question | What it defines |
> |---|----------|------------------|
> | Q1 | What defines this AI's core identity? | Identity channel — how the AI sees itself |
> | Q2 | What does this AI protect above all else? | Value channel — what triggers the strongest reaction |
> | Q3 | What kind of input does this AI refuse to process? | Blocked channel — what gets rejected at the gate |
> | Q4 | What is this AI's default interaction style? | Social channel — how it engages with counterparts |
> | S1–S4 | Strength per question (1–5) | 1 = minimal, 3 = moderate (default), 5 = absolute |
> | +1 | Free-text description (optional) | Backstory, sealed topics, emotional triggers |
>
> 4 questions × 4 options × 5 strength levels = 160,000 patterns. Strength controls how intensely each channel reacts — from a gentle note (1) to a full shutdown (5). Strength parameters are optional — omit them to use the default (3).
>
> ## Quick start
>
> ### 1. Get a constraint JSON
>
> **Option A — Form UI (recommended for first-time users)**
>
> Visit [fiveengine.dev/form](https://fiveengine.dev/form), answer the questions, and click Generate. No code required.
>
> **Option B — API call**
>
> ```
> POST https://fiveengine.dev/generate
> ```
>
> ```json
> {
>   "character_name": "Tsundere Weapon Shop Owner",
>   "q1": "A",
>   "q2": "B",
>   "q3": "A",
>   "q4": "C",
>   "s1": 3,
>   "s2": 4,
>   "s3": 5,
>   "s4": 2,
>   "free_text": "A gruff weapon shop owner. Lost a daughter in the war. Greedy with adults but soft with children."
> }
> ```
>
> Strength parameters (`s1`–`s4`) are optional. Omit them to use the default (3).
>
> The API returns a FIVE constraint JSON. $1 per call, one-time purchase.
>
> ### 2. Use the output (Method A — Quick Start)
>
> Paste the JSON directly into your LLM's system prompt. Works with any model that reads JSON: ChatGPT, Claude, Llama, Mistral, etc.
>
> ### 3. Use the harness (Method B — Production)
>
> For stronger structural consistency, use the FIVE Harness SDK to pre-classify every user input before it reaches the LLM.
>
> ```bash
> cp harness/five_harness.py your_project/
> ```
>
> ```python
> from five_harness import load_constraint, stage1_keyword, transform_input
>
> constraint = load_constraint("my_character.json")
> user_input = "I heard you lost your daughter in the war."
>
> hits = stage1_keyword(user_input, constraint)
> signal = transform_input(user_input, hits, constraint)
> # Feed `signal` to your LLM instead of raw user_input
> ```
>
> The harness uses a two-stage classifier:
> 1. **Stage 1 — Keyword match**: Fast, deterministic. Catches obvious triggers.
> 2. **Stage 2 — LLM classification**: Fallback for anything Stage 1 misses. Plug your own LLM call here.
>
> ## Demos
>
> Each demo folder contains an `input.json` (the form answers) and an `output.json` (the constraint rule FIVE generates). Browse them to see what the API produces.
>
> | Folder | Use case | Q1 | Q2 | Q3 | Q4 | Strength |
> |--------|----------|----|----|----|----|----------|
> | `npc_shopkeeper` | Game NPC | A: Role | B: Territory | A: Sealed contexts | C: Minimal | All 3 |
> | `chatbot_concierge` | Customer-facing chatbot | A: Role | C: Standards | B: Competence challenges | B: Professional | All 3 |
> | `agent_code_reviewer` | Autonomous agent | B: Belief | C: Standards | C: Out-of-scope demands | C: Minimal | All 3 |
> | `companion_wellness` | Personal companion | C: Relationship | A: People | A: Sealed contexts | A: Open | All 3 |
> | `vtuber_luna` | VTuber / streaming persona | A: Role | D: Self-consistency | D: Specific entities | D: Adaptive | All 3 |
>
> 5 use cases, all generated from the same 4 questions + strength setting. The engine is universal — you define the character, not the category.
>
> ## Project structure
>
> ```
> FIVE/
>   README.md
>   LICENSE
>   harness/
>     five_harness.py       # Free SDK — input classifier + transformer
>   demos/
>     npc_shopkeeper/       # Game NPC example
>     chatbot_concierge/    # Customer service chatbot example
>     agent_code_reviewer/  # Code review agent example
>     companion_wellness/   # Personal companion example
>     vtuber_luna/          # VTuber persona example
> ```
>
> ## Requirements
>
> Python 3.8+. No external dependencies.
>
> ## API
>
> The FIVE API generates constraint JSONs. $1 per call, one-time purchase.
>
> → **[Generate via Form UI](https://fiveengine.dev/form)** — browser-based, no code required
> → **[API endpoint](https://fiveengine.dev)** — `POST /generate` for programmatic access
>
> ## Why FIVE matters in the agentic era
>
> In agentic workflows, character drift is a cost problem, not just a quality problem. When an LLM character breaks under pressure (long context, jailbreak attempts, emotional bait), agents typically retry with a stronger prompt — inflating inference cost.
>
> FIVE addresses this at the input layer:
>
> - **Persona drift retry elimination**: Constraint JSON anchors the character structurally, reducing the need for re-prompting.
> - **Inference cost optimization**: Each $1 JSON purchase pays for itself when agentic tasks would otherwise consume retries.
> - **MCP-native**: Available as an MCP server (`five-mcp` on PyPI). Agents can discover FIVE through Model Context Protocol registries and use it directly.
> - **Token cost reduction**: A single FIVE-constrained system prompt typically outperforms multi-turn correction prompts on token economy.
>
> Drop the JSON in your system prompt. Pre-classify input with the harness if you need stronger guarantees. The character holds.
>
> ## License
>
> Personal and non-commercial use is free. Commercial use requires the official FIVE API. Output JSONs are yours — use, modify, and distribute them however you like, including commercially. See [LICENSE](LICENSE) for details.
