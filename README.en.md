# Durable Preferences

**Long-term preference memory for AI agents. Forget individual meals, not a person's tastes.**

[繁體中文](README.md) · [Method](docs/METHOD.md) · [Visual-memory research](docs/IMAGE_MEMORY.md) · [Validation](docs/VALIDATION.md)

Version **0.2.0**. Research prototype. Python 3.10+, SQLite, standard library only.
Project initiator and requirements: **紀順文 (Ji Shun-Wen)**. AI-assisted implementation and testing.

## What it does

This is an executable memory Skill, not a character prompt or a general transcript archive.
It accumulates sparse user feedback into durable, editable preference states. Hosts can retrieve a compact,
scoped context packet before an agent response without searching the entire conversation history.
Food preferences and conversational style are the initial domains; the core is not tied to one model vendor.

## The method

1. The host binds identity, scope, provenance and event time. Natural-language classification is the host's responsibility.
2. The core validates and deduplicates structured signals.
3. Feedback enters a short 60-day candidate path and a long-horizon path. The latter keeps up to 16 unconsumed day groups and does not expire merely because calendar time passes.
4. At least four groups and 75% directional agreement are needed on the slow path. Fast and slow paths share consumption: one batch cannot be counted twice.
5. Existing stable values move by `P = P + 0.40 * (target - P)`. Confidence does not drive learning to zero.
6. Explicit corrections apply immediately; temporary overrides remain separate. Mention frequency is not liking.
7. `compile` selects scoped state using indexes; reading does not reinforce preferences.

These are testable heuristics, not calibrated psychological measurements or guaranteed optimal parameters.

## Visual memory: current capability vs research

Implemented: structured state plus a color atlas generated from exactly the same state.
Ordinary agent integration consumes JSON; the atlas is not a replacement for the database.
Image-native lossless encoding and direct vision-model reading are **research proposals**, not implemented or validated claims.
We invite comparisons using identical underlying data and tasks. Negative findings are welcome.

## Try locally

Run from a directory named `durable-preferences`:

```bash
python examples/demo.py
python tests/run_all.py --unit-only
python tests/acceptance_v020.py --root . --out reports/local-run/acceptance.json
```

Use a private database outside the repository. Host integrations must call the skill and provide persistent storage.
Copying SKILL.md alone does not install cloud hooks or automatically synchronize memories.
See [installation](docs/INSTALLATION.md) and [host integration](references/host-integration.md).

## Evidence and limitations

The original v0.2.0 artifacts report 124 passing unit/regression tests, 16 passing specified learning cases,
365,300 writes plus 365,300 context compilations over a simulated decade, and 120,000 additional synthetic turns.
The publication preparation independently reran the unit suite and learning cases; it did not rerun the full decade workload.
Local warm-cache measurements are workload-specific, not an SLA.

A 50% sign-flip exploration still produces overly strong directions in 4 of 24 runs.
There is no live-LLM evaluation of semantic classification, autonomous skill activation or personalized final answers.
Namespacing is not authentication; checksums are not signatures; deduplication storage still grows with events.
Old backups do not know about deletions that occurred later in another environment.

## Join the research

Use repository Issues or Discussions when enabled. See [RFC-0001](docs/RFC-0001-image-memory.md).
Proposals can explore color encoding, stable concept identifiers, image-native assets, controlled comparisons,
privacy, semantic classification and safe host integration. Do not post private conversations, live databases or keys.

## License status

The supplied prototype did not specify an open-source license. This publication preparation preserves that status;
no LICENSE has been silently added. Discuss ideas and reproducible counterexamples freely in the community spaces;
the maintainer should set the contribution/license policy before accepting third-party code.
