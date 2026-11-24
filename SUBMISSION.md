# Checkable Coordinator

**Pitch:** A small on-chain coordinator for federated learning: clients file hash receipts of their updates, anyone can prove a FedAvg step from those receipts, and peers stake ETH to accuse an outlier.

## The problem

A typical federated-learning round still trusts a central aggregator. Clients cannot prove that the published average is honest, or that a poisoned update was filed, and a false accusation is cheap if there is no stake to lose. The people this prototype is for are reviewers and builders who want that coordination story on chain, in Fe, without training a model or storing weights.

This is a working prototype, not a production coordinator and not a privacy-preserving federated-learning system.

## Approach

The core contribution is an EVM contract written in Fe, `FlRegistry` in the `fl_coord` ingot. During an open round, each client files a `keccak256` receipt of a synthetic four-coordinate update plus that update's L1 norm. After the round, anyone can open the vectors in calldata. The contract checks each opening against the stored hash, computes an integer FedAvg, and stores commitments to the sum, the average, and the participant set. A peer can bond an accusation against an outlier. If the norm is far from the median and the vote meets quorum, the accused stake is slashed and FedAvg can be revised without that update. A false accusation slashes the accuser's bond instead.

Bash and Foundry only drive the tour. There is no model training, no GPU, and no mainnet deploy. All fixtures are synthetic.

The contracts, tests, and tour scripts were first written on 2026-10-28, before the judged window. They were reconstructed and re-verified during the window. No new Fe protocol features were added after that 28 October scaffold. The declaration below says this plainly so the jury can score only work from 3–24 November 2026.

## Fe highlight

Stake is `Wei`. An update coordinate is `i64`. Those types do not add, so a slash bounty cannot be mixed up with a gradient. Handlers also name the effects they use. `Ledger` holds the `StorageMap` books and cannot emit a log or send ETH on its own. The handler that pays out a slash has to take `call` and `log`:

```fe
pub contract FlRegistry uses (ctx: Ctx, call: mut Call, log: mut Log) {
    mut ledger: Ledger,
    // ...
    Resolve { accusation_id } -> u8 uses (mut ledger, mut call, mut log) {
        let payout = ledger.resolve(accusation_id)
        send_payout(payout)
        // ...
    }
}
```

That split is the point of Fe's effect system: the books and the side effects are different capabilities. The same contract also uses `msg` / `recv` with `sol(...)` selectors, a `Phase` enum matched exhaustively, `Wei` arithmetic for bonds, `#[error]` / `#[event]`, a `Commitment` trait, `WordVec<N>` with a `where N > 0` predicate and a closure fold, and `#[test(balance = ...)]` for the in-EVM tour.

## Architecture

- `src/lib.fe` — `FlRegistry`: messages, events, payouts.
- `src/ledger.fe` — `StorageMap` books and the round state machine (empty, open, attested, settled).
- `src/agg.fe` — hashes, integer FedAvg, median, outlier rule.
- `src/slash.fe` — accusation verdicts, in `Wei`.
- `src/events.fe`, `src/errors.fe` — event and error types.
- `src/agent.fe` — test-only forwarder, because `fe test` sends every call from the test contract. On Anvil, ordinary accounts call `FlRegistry` directly.
- `src/tests.fe` — chapter tests and the full in-EVM tour.
- `scripts/e2e.sh` — menu and `--ci` driver (eight stages, teardown last).
- `scripts/anvil_tour.sh` — the same story on a local Anvil node (Osaka hardfork).
- `explorer/` — static Judge Tour site, live at https://fe-fl-kent-private.fly.dev/.

`attest` takes opened vectors in calldata, rejects a bad hash or score, and writes commitments plus the median score. `resolve` runs `slash::settle`: a non-outlier slashes the accuser; an outlier without quorum returns the bond; an outlier with quorum slashes the accused stake, pays half of the slash to the accuser, and keeps half as treasury. Vote bonds are always returned. `revise` recomputes FedAvg from the non-poisoned receipts. ETH payouts use `call.send_value` after storage is updated, so a failed transfer reverts the whole resolution.

## Build and test

```sh
fe --version   # The exact Fe version used: fe 26.5.0 (3dab95f)
fe test        # 20 tests, in-process EVM
fe build --out-dir out
./scripts/e2e.sh --ci
```

Install Fe 26.5.0 (not an unpinned "latest"):

```sh
curl -fsSL https://raw.githubusercontent.com/argotorg/fe/master/feup/feup.sh | bash -s -- --version v26.5.0
source ~/.fe/env
```

The Anvil chapter also needs Foundry (`anvil` and `cast`). Fe 26.5 targets the Osaka hardfork; the tour script starts `anvil --hardfork osaka`. This tree was re-verified on 2026-11-23 and again on 2026-11-24 with Foundry 1.8.4. See the project [README.md](README.md) and [WALKTHROUGH.md](WALKTHROUGH.md) for a fuller setup.

Project manifest: `fe.toml` (ingot name `fl_coord`, version `0.1.0`). The manifest schema has no toolchain field; `scripts/e2e.sh` refuses to run unless `fe --version` reports 26.5.0.

## Demo

A reproducible CLI example:

```sh
./scripts/e2e.sh --ci
```

Expected result: eight stages pass (toolchain, build, unit tests, chapter 1 receipts, chapter 2 FedAvg attest, chapter 3 poison vote and slash, full in-EVM tour plus Anvil, and teardown last). `./scripts/anvil_tour.sh` after `fe build` is the Anvil chapter alone. It uses Anvil's published development keys on a local node only. See the README demo for the step-by-step.

On 2026-11-24 this tree produced `fe test --jobs 1`: 20 passed, 0 failed; `./scripts/e2e.sh --ci`: 8 stages passed, 0 failed, with teardown last.

A hosted Judge Tour explorer is at https://fe-fl-kent-private.fly.dev/. It is ungated. It is a static walkthrough of the same eight-stage tour; Fe is not executed there. Source for that site is in [`explorer/`](explorer/). There is no video.

## Limitations

- At most four clients and four voters. Fixed arrays keep the ABI and the tests obvious.
- The L1 norm is stored in the clear. The vector is not, but this is not private federated learning.
- FedAvg is integer division toward zero on four `i64`s, a checkable stand-in, not a floating-point training step.
- The outlier rule is `|score - lower median| > 20`. It is deterministic and tested, not a robust statistic for real gradients.
- One accusation per accused client per round.
- The native Fe backend is experimental and is not used. The contract path is what `fe test` and Anvil run.
- No mainnet or testnet deploy. The hosted explorer at https://fe-fl-kent-private.fly.dev/ is a static walkthrough; it does not run Fe.
- Ideas sketched after the 28 October scaffold (a higher client cap, committing the L1 norm until a challenge, a second round with carried stake, gas notes on `attest`) were not implemented.

Fe 26.x is not production-ready. Do not deploy this with real money.

## Declaration

- **Pre-existing work:** The Fe contracts (`src/*.fe`), tests, `scripts/e2e.sh`, `scripts/anvil_tour.sh`, and the original walkthrough were written on 2026-10-28, before the judged window opened on 3 November 2026 00:00 UTC, as an exploratory prototype in a Cursor cloud agent (id `bc-12e4d95b-18fd-5153-9343-4b92563a04ed`). That work was not published to GitHub. There was no prior Fe codebase, and nothing here was forked from another contest entry. The only Fe code that is not original to this repository is the language and `std` that ship with the Fe 26.5.0 compiler.

  On 2026-11-11 (Asia/Hong_Kong), the tree was reconstructed onto a local workstation from that agent's applied diffs, including a compile fix for unlabeled internal parameters that had already been part of the 28 October draft. The reconstruction was re-verified with Fe 26.5.0. No new Fe protocol features (for example a weighted FedAvg digest, or parameterized quorum and challenge-evidence work that had been sketched as a possible window delta) were added to the contracts after the 28 October scaffold. Product naming as Checkable Coordinator, the MIT license file, and documentation cleanup also date from that reconstruction.

  Documentation updates, teardown as e2e stage 8, and the static Judge Tour explorer were prepared during the judged window. They do not add Fe protocol features beyond the 28 October scaffold.

  The jury should treat the 28 October scaffold as the starting point and score only substantial work completed between 3 November 2026 00:00 UTC and 24 November 2026 23:59 UTC.

- **Third-party code:** Fe 26.5.0 and its standard library, as published by the Fe project. Foundry (Anvil, Cast) for the optional local-node tour. Anvil's published development keys are used only against a local node and are not secrets. No other third-party source was copied into `src/`.

- **AI assistance:** The initial prototype, tests, Anvil script, and documentation were drafted on 2026-10-28 by a Cursor cloud agent working for Kent G Lau, PhD. Later reconstruction, documentation, and this contest submission pack were prepared with assistance from Cursor / Grok Bot. Kent G Lau, PhD is the author and the responsible human contact. Contest rules allow AI assistance if it is disclosed and the author can explain the resulting code. This paragraph is that disclosure.

## Team

Kent G Lau, PhD (solo).

## License

MIT. Copyright 2026 Kent G Lau, PhD. See [LICENSE](LICENSE).

## Submission commit

**Full commit SHA:** `acb6cc7e3d4fc377e14d88c57861b12acb89ac34`.

If any later documentation-only commits are added on top of this tree, the form should use the tip of `main` at submission time (`git rev-parse HEAD`), not only the SHA above.
