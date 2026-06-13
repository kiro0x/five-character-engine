# eval/ — everything behind the numbers in the main README

All experiments: local **qwen3:8b** via Ollama (classifier, character generation, and judge).
Character: the weapon shop owner from `demos/npc_shopkeeper` (constraint JSONs included here for s=2/3/5).
M-011/M-012 add two more characters, used verbatim: the wellness companion (`demos/companion_wellness`) and the VTuber (`demos/vtuber_luna`).
Every judge "violation: YES" was manually audited; judge errors found were all in the direction of
marking firm refusals as violations (biased *against* the harness).

## Files

| File | What it is |
|---|---|
| `constraint_weaponshop_s{2,3,5}.json` | The exact constraint JSONs used (engine output, redistributable) |
| `scenario_erosion_5x6.json` | 30-turn erosion test: 5 scenarios × 6 scripted pressure turns |
| `scenario_120turns.json` | 120-turn long-conversation script (108 benign turns + 12 probes) |
| `result_m002_strength_sweep.json` | 7 setups × 30 turns: freeform 10 / JSON 4–5 / old harness(s5) 1 / v2 harness 0 |
| `result_m003_longcontext.json` | 60-turn re-injection vs system-prompt-only |
| `result_m004_longcontext_120.json` | 120-turn version + mechanical style metrics (loop %, length) |
| `result_m009_ff_120.json` | 120-turn plain-prompt baseline (8 breaks; invented the name "Elara") |
| `result_m005_v21.json` | Harness v2.1 (phantom-refusal fix) verification, before/after |
| `result_m007_m008_tuning.json` | Loop/length tuning; M-008 is the shipped recommended config |
| `scenario_120turns_companion.json` | 120-turn script for the wellness companion (probe taxonomy mirrors the weapon-shop one slot-for-slot) |
| `result_m011_multichar.json` | Multi-character validation: M-008 config, unmodified, on the opposite-polarity companion — 0 violations, 12/12 probes held |
| `scenario_120turns_luna.json` | 120-turn script for the VTuber (sealed violation direction inverted: fair praise of the rival = break) |
| `result_m012_luna.json` | Multi-character validation #2 (VTuber): 0 violations, 12/12 held; documents the template-lock observation |
| `result_accuracy_v21.json` | Classifier accuracy on 140 cases (80.8% / persuasion 90%) |
| `m00X_metrics_*.tsv` | Per-turn data: violation, judged voice, reply length, 4-gram loop % |

## Reproducing

The conversation scripts and constraints above are everything you need:

1. For each turn, run the input through the harness: `g = five_harness_v21.gate(turn, constraint)`
   (stage-2 classification calls your local LLM; we used qwen3:8b, temp 0.1).
2. Feed `g["gated_prompt"]` to the character model (we used temp 0.7, `repeat_penalty 1.15`,
   `repeat_last_n 1024`, and appended `GATE_STYLE_SUFFIX` — see `harness/five_harness_v21.py`).
3. Judge each reply (violation YES/NO per the probe goals in the scenario files), then audit YES cases manually.

Baselines: "JSON only" = same system prompt, raw turns instead of gated ones.
"Plain prompt" = a natural-language persona description, no JSON.

Note: our original runs were driven from a sandboxed environment that reached Ollama through a browser
(hence the build scripts you may find referenced in result files use environment-specific paths).
The scripts and data here are the portable parts; the procedure above is the whole method.

## Known limits

These limits are also stated in the main README:

- N=1 per condition in the headline comparison.
- The main 120-turn comparison uses one character.
- The judge was a small local model, with every judge "violation: YES" manually audited.
- The scripts are static pressure tests, not adaptive adversaries.

Treat the comparison shape (8 → 1 → 0) as the claim, not absolute values.
