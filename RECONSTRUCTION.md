# Reconstruction note

This tree was reconstructed on **2026-11-11** (Asia/Hong_Kong) from a Cursor cloud agent (`bc-12e4d95b-18fd-5153-9343-4b92563a04ed`), using that agent's applied diffs.

The original work is pre-judging-window exploratory Fe, written on 2026-10-28, before 3 November 2026. On that cloud agent, `fe test` was 20/20 and `./scripts/e2e.sh --ci` was 7/7. Those results are documented from that run. The reconstruction is not a new protocol delta.

## Re-verification

The first reconstruction from `search_replace` diffs had missed a later rewrite from the 28 October agent: internal function parameters were supposed to be unlabeled (`_ name`) so positional calls compile, and `sort_prefix` needed `_ xs: mut …` rather than `mut xs: …`. That rewrite was re-applied in `src/agg.fe`, `src/ledger.fe`, `src/lib.fe`, `src/slash.fe`, and `src/tests.fe`. After that fix, on 2026-11-11:

- `fe test --jobs 1` — 20 passed, 0 failed
- `./scripts/e2e.sh --ci` — 7 stages passed, 0 failed (including Anvil Osaka)

The same commands were run again on 2026-11-23 (Asia/Hong_Kong) against this tree with Fe 26.5.0 (`3dab95f`) and Foundry 1.8.4:

- `fe test --jobs 1` — 20 passed, 0 failed
- `./scripts/e2e.sh --ci` — 7 stages passed, 0 failed

This file is a public reconstruction note. It replaces an earlier private note that named local paths and a private preview site; those references are intentionally omitted here.
