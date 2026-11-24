# Checkable Coordinator

The Fe ingot remains `fl_coord`.

**Pitch:** A small on-chain coordinator for federated learning: clients file hash receipts of their updates, anyone can prove a FedAvg step from those receipts, and peers stake ETH to accuse an outlier.

The weak point of a typical federated-learning round is a trusted aggregator: without a checkable receipt, clients cannot prove that the average is honest or that a poisoned update was filed, and a false accusation is cheap if there is no stake to lose.

This is a Fe Builders Challenge prototype ([contest page](https://fe-lang.org/contest/), [announcement](https://blog.fe-lang.org/posts/fe-builders-challenge/)). The protocol lives in Fe. Bash and Foundry only drive the tour. There is no model training, no GPU, and no mainnet deploy. The jury-facing write-up, including the declarations the contest asks for, is in [SUBMISSION.md](SUBMISSION.md).

| | |
| --- | --- |
| Fe | **26.5.0** (`3dab95f`), the contest minimum |
| License | MIT, Copyright 2026 Kent G Lau, PhD |
| Status | Exploratory prototype first written on 2026-10-28, before the judged window. Reconstructed and re-verified during the window. No new Fe protocol features were added after the 28 October scaffold. |
| Submission commit | `3a3eca35c07286a0d68a8a5f8116dd2fce9b49b0` |

Fe 26.x is **not production-ready**. The Fe project says so, and this repo does not pretend otherwise. The contracts are a demo with tests, not a system to deploy with real money.

## What a round does

1. **Receipts.** A client registers with a stake and a public key commitment (a `u256`, not a name or other personal data). During an open round they submit `keccak256` of their update plus the update's L1 norm. The coordinate vector is not stored.
2. **FedAvg attest (BAFFLE-lite).** After the round, anyone submits the vectors in calldata. The contract checks each vector against the stored hash, computes an integer average, and stores commitments to the sum, the average, and the participant set. No trusted aggregator key.
3. **Poison vote.** A peer posts a bond and names an update. Other peers stake a vote. If the update's norm is far from the median **and** the vote meets quorum, the accused stake is slashed and the update is dropped. A false accusation slashes the accuser's bond instead. The average can then be revised without the poisoned update.

The story is domain-agnostic. The "update" is four `i64` coordinates, a stand-in for a gradient. Swap the fixture and the same registry fits any federated job. All fixtures in this repository are synthetic.

## Fe-specific highlight

Stake is `Wei`. An update coordinate is `i64`. Those types do not add. A slash bounty cannot be mixed up with a gradient, and the compiler rejects the mix. Handlers also name the effects they use, so a function that pays ETH or writes storage says so:

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

`Ledger` is a storage struct full of `StorageMap`s. It cannot emit a log or send ETH on its own. The handler has to pass `log` and `call`. That split is the point of Fe's effect system: the books and the side effects are different capabilities.

Other Fe 26.5 pieces used on purpose, not as decoration:

- `msg` / `recv` for the external interface, with `sol(...)` selectors
- `Phase` enum stored on chain and matched exhaustively
- `Wei` arithmetic for bonds (`bond / 2` is still `Wei`)
- `#[error]` reverts and `#[event]` logs
- a `Commitment` trait, and `WordVec<N>` with a `where N > 0` predicate and a closure fold
- `#[test]` plus `#[test(balance = ...)]` for the in-EVM tour

## Layout

```
fe.toml                 ingot manifest (compiler pin is documented here and checked by e2e)
src/agg.fe              hashes, integer FedAvg, median, outlier rule
src/slash.fe            accusation verdicts, in Wei
src/ledger.fe           StorageMap books and the round state machine
src/lib.fe              FlRegistry contract: messages, events, payouts
src/agent.fe            test-only forwarder so fe test can impersonate clients
src/events.fe           event types
src/errors.fe           custom errors
src/tests.fe            chapter tests and the full tour
scripts/e2e.sh          tour menu and --ci
scripts/anvil_tour.sh   same story on a local Anvil node
WALKTHROUGH.md          Fe from zero, then the map from chapters to files
SUBMISSION.md           contest write-up the jury is asked to start from
```

`Agent` exists because `fe test` sends every call from the test contract. Each simulated client is its own tiny contract that forwards to the registry. On Anvil, ordinary accounts call `FlRegistry` directly. Agent is not part of that path.

## Build and test

Install Fe **26.5.0** (not "latest" if latest has moved on):

```bash
curl -fsSL https://raw.githubusercontent.com/argotorg/fe/master/feup/feup.sh | bash -s -- --version v26.5.0
source ~/.fe/env
fe --version    # fe 26.5.0 (3dab95f)
```

Install Foundry for the Anvil chapter. Fe 26.5 targets the Osaka hardfork; the script starts `anvil --hardfork osaka`. This tree was re-verified on 2026-11-23 with Foundry 1.8.4 (`50af4efe`). It had earlier been run with Foundry 1.8.6 and 1.9.0 on other hosts.

```bash
curl -fsSL https://foundry.paradigm.xyz | bash
foundryup
```

From this directory:

```bash
fe test                 # 20 tests, in-process EVM
fe build --out-dir out  # out/FlRegistry.bin and FlRegistry.abi.json
./scripts/e2e.sh --ci   # toolchain, build, unit, chapters 1–3, Anvil
```

`./scripts/e2e.sh` with no arguments opens a menu when stdin is a terminal. Each stage writes `logs/e2e-<timestamp>/<stage>.log` and prints pass/fail plus seconds. The process exits 0 only if every stage passed.

A judge who only wants the chain story can run `./scripts/anvil_tour.sh` after `fe build`. It uses Anvil's published development keys, deploys `FlRegistry`, and checks scores, hashes, the average commitment, the slash, and the revised average. Those keys are not secret and must not be used anywhere else.

New to Fe? Read [WALKTHROUGH.md](WALKTHROUGH.md) first. It is written for someone who has never seen the language.

## Demo

There is no hosted frontend in this repository. The reproducible demo is the CLI tour:

```bash
./scripts/e2e.sh --ci
```

That run covers the toolchain pin, `fe build`, the unit tests, three chaptered in-EVM stories (receipts, FedAvg attest, poison vote and slash), and a local Anvil deployment of the same contract. `./scripts/anvil_tour.sh` is the Anvil chapter on its own.

On 2026-11-23, on a ThinkPad T14 running this tree, `fe test --jobs 1` was **20 passed, 0 failed** and `./scripts/e2e.sh --ci` was **7 stages passed, 0 failed**, with Fe 26.5.0 (`3dab95f`) and Foundry 1.8.4.

## Architecture

Clients are addresses with a `Wei` stake and a pubkey commitment. A round is an enum: empty, open, attested, settled. While the round is open, each client may file one receipt: a hash and an L1 score. `attest` takes the opened vectors in calldata, rejects any vector whose hash or score disagrees with storage, and writes three commitments plus the median score. `accuse` locks a bond against one receipt. `vote` locks a smaller bond for or against. `resolve` runs `slash::settle`: a non-outlier slashes the accuser; an outlier without quorum returns the bond; an outlier with quorum slashes the accused stake, pays half of the slash to the accuser, and keeps half as treasury. Vote bonds are always returned. `revise` recomputes FedAvg from the non-poisoned receipts and settles the round. ETH payouts use `call.send_value` after storage is updated, so a failed transfer reverts the whole resolution.

## Limitations

- At most four clients and four voters. Fixed arrays keep the ABI and the tests obvious. A longer round wants `DynArray`.
- The L1 norm is stored in the clear. The vector is not, but this is not private federated learning. Hiding the norm until a challenge is future work.
- FedAvg is integer division toward zero on four `i64`s. It is a checkable stand-in, not a floating-point training step.
- The outlier rule is `|score - lower median| > 20`. It is deterministic and tested. It is not a robust statistic for real gradients.
- One accusation per accused client per round. Registration stake and the accusation bond are separate pots.
- `fe test` does not fund `msg.sender` unless the test sets `#[test(balance = ...)]`. That attribute funds the test contract. Multi-client tests go through `Agent` for that reason.
- The native backend can build a hello-world executable on the 26.5.0 Linux binary, and it is still experimental. This demo does not use it. The contract path is what `fe test` and Anvil run.
- No proof-of-deletion, escrow, hashmirror, lineage channel, vertical FL, or agent-tool payments. Those were optional and are not in this prototype.
- No mainnet, no testnet deploy, and no frontend in this repository.
- Ideas sketched after the 28 October scaffold (a higher client cap, committing the L1 norm until a challenge, a second round with carried stake, gas notes on `attest`) were not implemented in this tree.

## Compiler caveats worth knowing

- Call arguments are labeled. A bare identifier is the label (`register(agent, 11)` does **not** compile). Parameters prefixed with `_` in this repo are unlabeled so the tour reads straight through. See `WALKTHROUGH.md`.
- `#[payable]` sits on the `recv` arm. A non-payable arm reverts if you attach ETH.
- Custom errors are `#[error]` structs. `revert_error(...)` ABI-encodes them.
- Storage is Solidity-compatible as of 26.5, and it is **not** compatible with bytecode built by 26.4.
- `assert!(false)` reverts with `Panic(0x01)`. Overflow reverts with `Panic(0x11)`.

## Declaration of prior work, third-party code, and AI assistance

See [SUBMISSION.md](SUBMISSION.md) for the full declaration. The short version:

- **Pre-existing work.** The Fe contracts, tests, and tour scripts were written on 2026-10-28, before the judged window opened on 3 November 2026 00:00 UTC. They were not published to GitHub. The tree was reconstructed and re-verified on 2026-11-11. No new Fe protocol features were added after the 28 October scaffold. Only substantial work completed from 3 November 2026 00:00 UTC through 24 November 2026 23:59 UTC is judged.
- **Third-party code.** Fe 26.5.0 and its standard library; Foundry (Anvil, Cast) for the local-node tour. Anvil's published development keys are used only on a local node. No other third-party source was copied into `src/`.
- **AI assistance.** A Cursor cloud agent drafted the 28 October prototype. Later reconstruction, documentation, and the contest write-up were prepared with assistance from Cursor / Grok Bot. Kent G Lau, PhD is the author and the responsible human contact.

## Team

Kent G Lau, PhD (solo).

## License

MIT. Copyright 2026 Kent G Lau, PhD. See [LICENSE](LICENSE).
