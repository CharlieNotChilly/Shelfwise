# Rules for AI coding agents (Claude Code, ChatGPT/Codex, and others)

This project backs specific résumé claims. Correctness and honesty matter more than speed.

## Before writing code
1. Read `docs/SPEC.md` (the contract), `docs/DESIGN.md` (architecture and decisions), and `docs/PLAN.md` (phases).
2. Work on **one phase at a time**, the one the user names. Do not start later phases or add features outside the spec.
3. If something in the spec seems wrong or impossible (for example, a Shopify API change), stop and say so. Do not silently change behavior or the stack.
4. Use the Shopify AI Toolkit / Shopify docs for current API details instead of guessing field names.

## While writing code
- Follow the data model, endpoints, cleaning rules, and backtest definition in DESIGN.md exactly.
- Fix SKU selection, feature scaling (if used), and model settings before the test window. At each monthly rolling-origin refit, training may include completed test-window weeks strictly before the forecast week. Use only observations available before each weekly forecast.
- Respect Shopify limits: at most 5 new orders per minute on the dev store, and every GraphQL call goes through the cost-aware client.
- Every phase ends with tests for its spec criteria (the IDs in SPEC.md). Run them and show the output.
- Never commit API secrets, access tokens, or the raw dataset.

## Results and numbers
- **Never invent, estimate, or round up results.** Every number in the README or SPEC must come from a file in `results/`.
- Do not change the fixed parameters in SPEC.md (500 SKUs, 52 test weeks, WAPE, 4-week moving-average baseline, 1,000 seeded orders).
- If the model loses to the baseline or a test fails, report it plainly. Do not tune on the test window to hide it.

## When a phase is done
- Summarize what changed, which spec criteria now pass, and anything still failing.
- Suggest a commit message (plain text, no AI attribution).
