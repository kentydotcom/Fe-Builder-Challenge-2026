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
| Submission commit | `acb6cc7e3d4fc377e14d88c57861b12acb89ac34` |

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
scripts/e2e.sh          tour menu and --ci (eight stages, teardown last)
scripts/anvil_tour.sh   same story on a local Anvil node
WALKTHROUGH.md          Fe from zero, then the map from chapters to files
SUBMISSION.md           contest write-up the jury is asked to start from
explorer/               static Judge Tour site (live at https://fe-fl-kent-private.fly.dev/)
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
./scripts/e2e.sh --ci   # stages 1–8, ending with teardown
```

`./scripts/e2e.sh` with no arguments opens a menu when stdin is a terminal. Use the menu to run one stage, or item 9 to run all eight in order (teardown last). Each stage writes `logs/e2e-<timestamp>/<stage>.log` and prints pass/fail plus seconds. The process exits 0 only if every requested stage passed.

A judge who only wants the chain story can run `./scripts/anvil_tour.sh` after `fe build`. It uses Anvil's published development keys, deploys `FlRegistry`, and checks scores, hashes, the average commitment, the slash, and the revised average. Those keys are not secret and must not be used anywhere else.

New to Fe? Read [WALKTHROUGH.md](WALKTHROUGH.md) first. It is written for someone who has never seen the language.

## Demo

A hosted Judge Tour explorer is at [https://fe-fl-kent-private.fly.dev/](https://fe-fl-kent-private.fly.dev/). It is ungated. It is a static, phone-first walkthrough of the same eight-stage tour (teardown last). Fe and Anvil are not executed there. Source for that site is in [`explorer/`](explorer/).

The reproducible run is the CLI tour driven by `scripts/e2e.sh`. It does not train a model and does not talk to a public network. Follow the steps in order.

### 1. Install the toolchain

You need Fe **26.5.0** exactly (not an unpinned "latest") and Foundry, because the last chapters start a local Anvil node on the Osaka hardfork.

```bash
curl -fsSL https://raw.githubusercontent.com/argotorg/fe/master/feup/feup.sh | bash -s -- --version v26.5.0
source ~/.fe/env
fe --version    # expect: fe 26.5.0 (3dab95f)

curl -fsSL https://foundry.paradigm.xyz | bash
foundryup
anvil --version
```

`scripts/e2e.sh` puts `~/.fe/bin` and `~/.foundry/bin` on `PATH` for you, but the binaries still have to be installed.

### 2. Get the repository and enter it

```bash
git clone https://github.com/kentydotcom/Fe-Builder-Challenge-2026.git
cd Fe-Builder-Challenge-2026
```

If you already have a checkout, `cd` to that directory instead. All later commands are run from the repository root (the folder that contains `fe.toml` and `scripts/e2e.sh`).

### 3. Pick how to run the tour

The same eight stages run either way. The script exits 0 only if every stage it was asked to run has passed.

**Unattended (what most judges, and CI, should use):**

```bash
./scripts/e2e.sh --ci
```

`--all` is the same as `--ci`. If stdin is not a terminal, `./scripts/e2e.sh` with no arguments also runs every stage.

**Interactive menu** (when you are at a terminal and want to go chapter by chapter):

```bash
./scripts/e2e.sh
```

You will get:

```
Checkable Coordinator
  1  toolchain check (Fe 26.5.0)
  2  build
  3  unit tests (FedAvg, hashes, slash math)
  4  chapter 1 — receipts
  5  chapter 2 — FedAvg attest
  6  chapter 3 — poison vote and slash
  7  full tour (in-EVM test + Anvil)
  8  teardown (stop leftover Anvil, keep logs)
  9  run all
  q  quit
```

Type `1`–`8` to run that stage alone, `9` to run all eight in order (teardown last), or `q` to leave. One stage at a time is useful if you want to read a chapter before the next one. `--stage N` does the same thing without the menu, for example `./scripts/e2e.sh --stage 4` for receipts only.

A passing `--ci` run already starts and stops Anvil itself. You do not have to run `./scripts/anvil_tour.sh` as well. That script is only if you want the on-chain story by itself, after `fe build --out-dir out`. It uses Anvil's published development keys on a local node; those keys are not secret and must not be used anywhere else.

### 4. What each stage does

| # | Stage | What it checks |
| --- | --- | --- |
| 1 | toolchain | `fe --version` is 26.5.0, and `cast` / `anvil` are on `PATH` |
| 2 | build | `fe build --out-dir out`, then `out/FlRegistry.bin` and `out/FlRegistry.abi.json` exist |
| 3 | unit | Pure FedAvg, hash, and slash tests (`fe test --filter test_unit`) |
| 4 | chapter 1 | Register clients, open a round, submit receipt hashes |
| 5 | chapter 2 | Anyone can attest; the contract recomputes integer FedAvg |
| 6 | chapter 3 | Poison vote, slash, and a revised average without the outlier |
| 7 | tour | The full in-EVM story, then the same story on a local Anvil node (`./scripts/anvil_tour.sh`). Anvil listens on `127.0.0.1:18545` and is stopped when that script exits |
| 8 | teardown | **Always last** in `--ci` and in menu item 9. It confirms Anvil is gone, removes a leftover `.anvil.pid` or `/tmp/fl-anvil.log` if one is still there, and leaves `logs/e2e-*` alone. It is safe if nothing is running: that is a pass, not a skip |

A failure in one stage does not skip the later ones. Teardown still runs at the end of `--ci` so a failed tour cannot leave a node behind. The overall exit code is non-zero if any stage failed.

### 5. Where the logs go

Each run makes a fresh directory, `logs/e2e-<UTC-timestamp>/`, with one log file per stage (`toolchain.log`, `build.log`, …, `teardown.log`). That folder is gitignored. Teardown does not delete the current run's logs, or older `logs/e2e-*` directories.

If a stage fails, the script prints the path and the last lines of that stage's log.

### 6. What a passing run looks like

The printed summary at the end should have eight `PASS` lines, teardown last, and this footer:

```
PASS  8 stages, 0 failed
```

Times will vary by machine. The stage names and the count of eight should not. The process exit code is 0.

On 2026-11-24, on a ThinkPad T14 running this tree, `fe test --jobs 1` was **20 passed, 0 failed** and `./scripts/e2e.sh --ci` was **8 stages passed, 0 failed**, with teardown last, Fe 26.5.0 (`3dab95f`), and Foundry 1.8.4.

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
