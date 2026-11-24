# Fe, from nothing, then this project

You do not need to have written Fe before. This file gets a compiler onto the machine, runs a twenty-line contract, and then walks the federated-learning judge tour file by file.

The contest asks for Fe **26.5.0 or newer**. This repo is pinned to **26.5.0** exactly, so a judge and you run the same compiler. Check with `fe --version`. It should print `fe 26.5.0` and a short commit (`3dab95f` for the release this prototype was built with).

Fe looks like Rust and compiles to EVM bytecode. A contract does not have Solidity `function`s. It has a `msg` enum (the ABI) and a `recv` block (the code that runs when a message arrives). Effects such as "I am writing storage" or "I am sending ETH" are written in the signature. The compiler rejects a handler that touches storage without saying so.

Fe 26.x is not production-ready. The team says that in the compiler README. Learn it here. Do not point it at mainnet.

## 1. Install Fe 26.5.0

Linux or macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/argotorg/fe/master/feup/feup.sh | bash -s -- --version v26.5.0
source ~/.fe/env
fe --version
```

`feup` installs `fe` into `~/.fe/bin`. The `source` line adds that directory to `PATH` for the current shell. Put the same `source ~/.fe/env` in your shell profile if you want it every time.

Homebrew also has a tap (`brew install fe-lang/tap/fe`). Prefer the `feup` command above when you need this exact version.

The Anvil half of the tour needs Foundry. Fe 26.5 targets the Osaka hardfork, so the node has to understand Osaka:

```bash
curl -fsSL https://foundry.paradigm.xyz | bash
foundryup
anvil --version
```

This prototype was checked with Foundry 1.8.6.

## 2. Hello, contract

Do this in `/tmp`, not in the project directory. `fe new` refuses to overwrite an existing `fe.toml`, and the project already has one.

```bash
mkdir -p /tmp/fe-hello
cd /tmp/fe-hello
fe new counter
cd counter
fe test
fe build --out-dir /tmp/fe-hello-out
ls /tmp/fe-hello-out
```

`fe test` compiles every `#[test]` and runs it in a built-in EVM. No node. `fe build` writes three files per contract:

- `Counter.bin` — init bytecode, what you deploy
- `Counter.runtime.bin` — the code stored on chain
- `Counter.abi.json` — a Solidity-compatible ABI

Open `src/lib.fe`. The scaffold is a counter. The pieces you will see again in the registry:

```fe
msg CounterMsg {
    #[selector = sol("increment()")]
    Increment,
    #[selector = sol("get()")]
    Get -> u256,
}

struct CounterStore {
    value: u256,
}

pub contract Counter {
    mut store: CounterStore

    init() uses (mut store) {
        store.value = 0
    }

    recv CounterMsg {
        Increment uses (mut store) {
            store.value = store.value + 1
        }
        Get -> u256 uses (store) {
            store.value
        }
    }
}
```

Read it as:

- `msg` is the public interface. `sol("get()")` is the Solidity selector, computed at compile time, so `cast` can call `get()`.
- `struct CounterStore` is the storage layout. It is persisted between calls.
- `mut store` on the contract is the storage field. `mut` means handlers may write it.
- `init` is the constructor. `uses (mut store)` is the effect: this code writes storage.
- `Get` only `uses (store)`, so it cannot write. `Increment` can.
- The last expression of a handler is the return value. `Get` returns `store.value`.

There are no semicolons. `var` is a mutable local. `let` is immutable.

### A test

The scaffold's test deploys with `create2` and calls the message enum. That is the same pattern as `src/tests.fe` in this repo:

```fe
#[test]
fn test_counter() uses (evm: mut Evm) {
    let addr = evm.create2<Counter>(value: Wei::zero(), args: (), salt: 0)
    let val: u256 = evm.call(
        addr: addr,
        gas: 100000,
        value: Wei::zero(),
        message: CounterMsg::Get {},
    )
    assert!(val == 0)
}
```

`uses (evm: mut Evm)` gives the test the right to deploy and call. `assert!` reverts the test on failure. `Wei::zero()` is zero ETH. `Wei` is not a plain integer; the next section is why that matters.

### Optional: a native executable

Fe 26.5 can also emit a host executable. It is experimental. **This project does not use it.** The judge tour is the EVM contract, `fe test`, and Anvil. If you want to see the other backend once:

```bash
echo 'pub fn main() -> i32 { 0 }' > /tmp/hello_native.fe
fe build --backend native --out-dir /tmp/fe-native-out /tmp/hello_native.fe
/tmp/fe-native-out/hello_native; echo exit:$?
```

On the x86-64 Linux build of Fe 26.5.0 that command writes an executable and the process exits 0. If it does not on your machine, ignore it and stay with the contract.

## 3. How a Fe project is laid out

```
fe.toml          the ingot (Fe's word for a package)
src/lib.fe       crate root. Contracts and msgs here are the root module.
src/agg.fe       module `agg`. From lib.fe you write `use agg::fedavg`.
src/ledger.fe    module `ledger`
```

`fe.toml` for this repo:

```toml
[ingot]
name = "fl_coord"
version = "0.1.0"
```

The manifest has no field for the compiler version. 26.5.0 ignores unknown keys. The pin lives in the comment at the top of `fe.toml`, in this file, and in `scripts/e2e.sh`, which refuses to run unless `fe --version` contains `26.5.0`.

From a child file, the parent module is `super`:

```fe
use super::FlMsg
```

That is `src/agent.fe` importing the message enum declared in `src/lib.fe`.

## 4. The types this demo actually uses

### Integers, and why stake is not an integer

`u256` is the EVM word. `i64` is a signed coordinate. `Wei` is an amount of ETH. `Wei + i64` does not compile. `Wei / 2` is still `Wei`. That is the property the slash code relies on (`src/slash.fe`):

```fe
let half = input.accuser_bond / 2
let rest = input.accuser_bond - half
```

`ether(1)`, `wei(1000)`, and `Wei::zero()` construct amounts. `amount.as_wei()` gives the raw `u256` when a getter has to return a plain integer to `cast`.

### Addresses

`Address::new(word)` checks that the word fits in 160 bits. `Address::zero()` is the zero address. `address.word()` is the `u256`. The registry rejects the zero address as a client.

### Structs, enums, traits

`Coords` in `src/agg.fe` is the fake gradient: four `i64`s. `Phase` in `src/ledger.fe` is the round state machine (`Empty`, `Open`, `Attested`, `Settled`). It is stored inside the round record. A `match` has to cover every variant; forgetting `Settled` is a compile error.

`trait Commitment` gives `Coords` a `commit()` method that keccak-hashes the four words. Traits are how you hang an operation off a type without making it a method of every integer.

`WordVec<const N: usize> where N > 0` is a const-generic vector. `WordVec<0>` is rejected at compile time. `sum` folds it with a closure (`|acc, word| acc + word`), which is new in 26.5. The test is `test_unit_wordvec_fold`.

### StorageMap

A map is not a memory `HashMap`. It is a contract storage collection, keyed like a Solidity `mapping` (`keccak256(key ++ slot)`).

```fe
pub clients: StorageMap<Address, Client>,
pub receipts: StorageMap<(u256, Address), Receipt>,
```

`get` copies the value out (the value type has to be `Copy`). `set` writes it back. Missing keys read as zero: a missing client is `registered: false` and `stake: Wei::zero()`. The round enum's first variant is `Empty`, which is also what a zeroed slot decodes as, so a round nobody has opened is empty.

The maps live on one struct, `Ledger`, which is the contract's only storage field (`mut ledger: Ledger` in `src/lib.fe`). Methods on `Ledger` take `mut self` when they write. That is the same shape as the standard library's own storage examples.

### Messages, payable, events, errors

`FlMsg` in `src/lib.fe` is the whole ABI. `#[payable]` is written on the arm inside `recv`, not on the message variant. `register` is payable. `openRound` is not. Sending ETH to a non-payable arm reverts.

```fe
#[event]
pub struct ReceiptSubmitted {
    #[indexed]
    pub round_id: u256,
    #[indexed]
    pub client: Address,
    pub update_hash: u256,
    pub score: u256,
}
```

Indexed fields become log topics. The handler emits with `log.emit(...)`, and it must `uses (..., mut log)`.

Failures are `#[error]` structs in `src/errors.fe`. `revert_error(StakeTooSmall { sent, required })` reverts with a Solidity custom error. `fe test` prints the selector and the ABI payload when a test reverts.

### Labels on calls

Fe call arguments are labeled. `hash_update(round_id: 1, client: 9, coords)` is the explicit form. A bare name is sugar for a label: `hash_update(round_id, client, coords)` works only when the local variables are already named `round_id`, `client`, and `coords`.

`hash_update(1, 9, coords)` does **not** compile against a normal parameter. This repo writes internal parameters as `_ round_id`, which drops the label, so the tests can pass values positionally. Standard library calls stay labeled: `evm.call(addr: ..., gas: ..., value: ..., message: ...)`.

### Tests and ETH

`#[test]` is enough for pure functions (`src/agg.fe`, `src/slash.fe`).

A test that deploys a contract adds `uses (evm: mut Evm)`.

A test that sends ETH also needs a balance. The test runner's caller starts at zero. This attribute funds the **test contract**, which is `msg.sender` for the calls it makes:

```fe
#[test(balance = 5000000)]
fn test_stage1_register_open_submit() uses (evm: mut Evm) { /* ... */ }
```

`#[test(should_revert)]` passes when the test reverts. Use it for "the second submit must fail". Pair it with a normal test of the happy path, because a revert during setup would also satisfy `should_revert`.

## 5. The judge tour, chapter by chapter

One round, four clients. Coordinates:

| client | vector | L1 score | role |
| --- | --- | --- | --- |
| A | `(1, 2, 3, 4)` | 10 | honest |
| B | `(2, 2, 3, 4)` | 11 | honest |
| C | `(1, 1, 3, 5)` | 10 | honest |
| D | `(40, 40, 40, 40)` | 160 | outlier |

The lower median of `[10, 10, 11, 160]` is `10`. The bound is `20`, so only D is an outlier. Integer FedAvg of all four averages to `(11, 11, 12, 13)`. Without D it averages to `(1, 1, 3, 4)`.

### Receipts

What happens: clients register with stake, someone opens round `7`, each client submits a hash and a score. Storage keeps the hash and the score. It does not keep the four coordinates.

| | |
| --- | --- |
| Hash and L1 | `hash_update`, `l1` in `src/agg.fe` |
| Books | `Ledger::register`, `open_round`, `submit` in `src/ledger.fe` |
| ABI and events | `Register`, `OpenRound`, `SubmitReceipt` in `src/lib.fe` |
| Tests | `test_stage1_register_open_submit`, `test_stage1_low_stake`, `test_stage1_double_submit` |
| Anvil | the "chapter 1" echoes in `scripts/anvil_tour.sh` |

`submit` appends the caller to `round.clients` and increments `receipt_count`. A second submit from the same client reverts with `AlreadySubmitted`. A stake below `min_stake` reverts with `StakeTooSmall`.

### FedAvg, no trusted aggregator

What happens: anyone calls `attest` with the four vectors. For each client the contract recomputes the L1 and the hash. A mismatch reverts (`ScoreMismatch` or `HashMismatch`). If the set is exactly the set that submitted, it stores:

- `sum_commitment` — keccak of the four `i256` sums
- `avg_commitment` — keccak of the four average `i64`s
- `set_commitment` — keccak of the sorted client addresses
- `median_score` — for the poison rule

The vectors are calldata. They are not written into the maps.

| | |
| --- | --- |
| Math | `fedavg`, `median`, `participant_commitment` in `src/agg.fe` |
| Checks | `Ledger::attest` → `open_and_check` in `src/ledger.fe` |
| ABI | `Attest`, `PreviewAverage`, `AvgCommitment` in `src/lib.fe` |
| Tests | `test_stage2_attest_fedavg` (commitment equals `previewAverage` and the pure function), `test_stage2_bad_opening` |
| Anvil | "chapter 2" in `scripts/anvil_tour.sh` |

`previewAverage` is a pure function on the contract so the shell script can ask the chain what the commitment should be, instead of reimplementing keccak in bash.

There is no aggregator key. The check is "these openings match the receipts, and this is the average." Anyone can submit the openings.

### Poison vote, slash, revise

What happens:

1. After attestation, client A posts `bond` and accuses D.
2. Client B posts `vote_bond` in support.
3. Anyone calls `resolve`.
4. D's norm is an outlier and there is one support vote with more support stake than oppose stake, so the verdict is **upheld** (code `1`). D's registration stake drops by `slash_amount`. Half of that slash is paid to A on top of A's returned bond. The other half stays in the contract as `treasury`. D's receipt is marked `poisoned`.
5. `revise` opens only A, B, and C. The new average commitment is the honest FedAvg. The round becomes `Settled`.

The other two verdicts, both tested:

- **False accusation** (code `2`). Accusing B, whose score is `11`, fails the outlier check even if people would have voted yes. A's bond is slashed: half to B, half to treasury. B's registration stake is untouched.
- **Failed quorum** (code `3`). Accusing D but nobody votes. The accusation was not false, it was unsupported. A's bond is returned. D is not slashed.

| | |
| --- | --- |
| Verdict math | `settle` in `src/slash.fe` |
| State machine | `accuse`, `vote`, `resolve`, `revise` in `src/ledger.fe` |
| ETH movement | `send` / `send_payout` in `src/lib.fe` |
| Tests | `test_stage3_upheld_slash_and_revise`, `test_stage3_false_accusation`, `test_stage3_failed_quorum`, `test_stage3_self_accusation`, `test_tour_judge_full` |
| Anvil | "chapter 3" in `scripts/anvil_tour.sh` |

`test_tour_judge_full` is the whole story in one test, and it checks the contract's ETH balance after payouts (`3750` wei with the small test stakes). The Anvil script uses 1 ether stakes so the numbers are readable on a chain, and checks the same ratios.

### Why `src/agent.fe` exists

`fe test` has one sender: the test contract. The registry keys clients by `ctx.caller()`. The tour deploys four `Agent` contracts and calls those. Each agent forwards `register`, `submit`, `accuse`, and `vote` to the registry, so the registry sees four callers.

Agents also have a payable fallback (`recv { #[payable] _ {} }`) so a slash payout of bare ETH does not bounce.

On Anvil you skip Agent. Accounts 1–4 call `FlRegistry` themselves. Account 0 deploys and can attest, because attestation is permissionless.

## 6. Run it

From the repository root, with `fe` and `anvil` on `PATH`:

```bash
fe test
fe build --out-dir out
./scripts/e2e.sh --ci
```

The menu (`./scripts/e2e.sh` in a terminal) runs the same stages one at a time. Logs land in `logs/e2e-<timestamp>/`. That directory is gitignored.

`./scripts/e2e.sh --stage 4` is chapter 1 only. Stage numbers are printed by `--help`.

## 7. What this file is not

It is not a full language reference. The guide at https://fe-lang.org/getting-started/first-contract/ is the official one, and it is the right next read after the counter above. This file only covers the slice the registry uses, so you can change a chapter without learning the whole compiler first.
