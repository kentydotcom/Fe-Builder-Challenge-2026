#!/usr/bin/env bash
# Anvil chapter of the Checkable Coordinator tour.
#
# Deploys FlRegistry to a local Anvil node (Osaka hardfork, the Fe 26.5 target)
# and walks the same story as `test_tour_judge_full`, using four funded
# accounts instead of the in-test Agent forwarder.
#
# The private keys below are Anvil's published development keys. They are not
# secret. Do not use them anywhere but this local node.
#
# Environment:
#   ANVIL_RPC   reuse an already-running node (the script will not kill it)
#   ANVIL_PORT  port when this script starts Anvil (default 18545)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.foundry/bin:${HOME}/.fe/bin:${PATH}"

if ! command -v cast >/dev/null || ! command -v anvil >/dev/null; then
  echo "anvil and cast are required. Install Foundry: https://book.getfoundry.sh/getting-started/installation" >&2
  exit 1
fi

if [[ ! -f out/FlRegistry.bin ]]; then
  echo "missing out/FlRegistry.bin; run \`fe build --out-dir out\` first" >&2
  exit 1
fi

PORT="${ANVIL_PORT:-18545}"
RPC="${ANVIL_RPC:-http://127.0.0.1:${PORT}}"
STARTED_ANVIL=0
ANVIL_PID=""

cleanup() {
  if [[ "$STARTED_ANVIL" == 1 && -n "$ANVIL_PID" ]]; then
    kill "$ANVIL_PID" >/dev/null 2>&1 || true
    wait "$ANVIL_PID" >/dev/null 2>&1 || true
  fi
  rm -f "${ROOT}/.anvil.pid"
}
trap cleanup EXIT

if [[ -z "${ANVIL_RPC:-}" ]]; then
  anvil --host 127.0.0.1 --port "$PORT" --hardfork osaka --silent >/tmp/fl-anvil.log 2>&1 &
  ANVIL_PID=$!
  STARTED_ANVIL=1
  echo "$ANVIL_PID" > "${ROOT}/.anvil.pid"
  ready=0
  for _ in $(seq 1 50); do
    if cast chain-id --rpc-url "$RPC" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 0.1
  done
  if [[ "$ready" != 1 ]]; then
    echo "anvil did not start; log:" >&2
    cat /tmp/fl-anvil.log >&2 || true
    exit 1
  fi
fi

# Anvil development accounts 0..4. Account 0 deploys. Accounts 1..4 are clients.
ADMIN_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
K1=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
K2=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
K3=0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6
K4=0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a

A1=$(cast wallet address --private-key "$K1")
A2=$(cast wallet address --private-key "$K2")
A3=$(cast wallet address --private-key "$K3")
A4=$(cast wallet address --private-key "$K4")

ETH=1000000000000000000
STAKE=$ETH
BOND=$ETH
VOTE=250000000000000000
SLASH=500000000000000000
ROUND=7

bytecode="0x$(tr -d '[:space:]' < out/FlRegistry.bin)"
ctor=$(cast abi-encode "constructor(uint256,uint256,uint256,uint256)" "$STAKE" "$BOND" "$VOTE" "$SLASH")
init="${bytecode}${ctor#0x}"

deploy_json=$(cast send --private-key "$ADMIN_KEY" --rpc-url "$RPC" --json --create "$init")
REG=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["contractAddress"])' "$deploy_json")
echo "deployed FlRegistry at ${REG}"

need() {
  local got="$1"
  local expected="$2"
  local label="$3"
  if [[ "$got" != "$expected" ]]; then
    echo "FAIL ${label}: got '${got}' expected '${expected}'" >&2
    exit 1
  fi
  echo "ok   ${label}"
}

call() {
  # cast prints `123 [1.23e2]` for integers. Keep the raw word.
  cast call --rpc-url "$RPC" "$REG" "$@" | awk '{print $1}'
}

send() {
  local key="$1"
  shift
  cast send --private-key "$key" --rpc-url "$RPC" "$REG" "$@" >/dev/null
}

# Views are pure, so the script asks the contract for hashes instead of
# reimplementing keccak. The coordinates are the same fixtures as the Fe tests:
# three small updates and one large outlier (L1 160).
score_of() {
  call "scoreOf(int64,int64,int64,int64)(uint256)" "$1" "$2" "$3" "$4"
}
hash_of() {
  local client="$1"
  shift
  call "hashOpening(uint256,address,int64,int64,int64,int64)(uint256)" "$ROUND" "$client" "$@"
}

S1=$(score_of 1 2 3 4)
S2=$(score_of 2 2 3 4)
S3=$(score_of 1 1 3 5)
S4=$(score_of 40 40 40 40)
need "$S1" 10 "client1 L1"
need "$S2" 11 "client2 L1"
need "$S3" 10 "client3 L1"
need "$S4" 160 "client4 L1"

H1=$(hash_of "$A1" 1 2 3 4)
H2=$(hash_of "$A2" 2 2 3 4)
H3=$(hash_of "$A3" 1 1 3 5)
H4=$(hash_of "$A4" 40 40 40 40)

echo "chapter 1: register clients and open the round"
send "$K1" --value "$STAKE" "register(uint256)" 11
send "$K2" --value "$STAKE" "register(uint256)" 12
send "$K3" --value "$STAKE" "register(uint256)" 13
send "$K4" --value "$STAKE" "register(uint256)" 14
need "$(call "registered(address)(bool)" "$A1")" true "client1 registered"
need "$(call "stakeOf(address)(uint256)" "$A1")" "$STAKE" "client1 stake"
send "$ADMIN_KEY" "openRound(uint256)" "$ROUND"
need "$(call "phase(uint256)(uint8)" "$ROUND")" 1 "round open"

echo "chapter 1: submit receipt hashes (no weights stored)"
send "$K1" "submitReceipt(uint256,uint256,uint256)" "$ROUND" "$H1" "$S1"
send "$K2" "submitReceipt(uint256,uint256,uint256)" "$ROUND" "$H2" "$S2"
send "$K3" "submitReceipt(uint256,uint256,uint256)" "$ROUND" "$H3" "$S3"
send "$K4" "submitReceipt(uint256,uint256,uint256)" "$ROUND" "$H4" "$S4"
need "$(call "receiptCount(uint256)(uint256)" "$ROUND")" 4 "four receipts"
need "$(call "updateHash(uint256,address)(uint256)" "$ROUND" "$A4")" "$H4" "outlier hash stored"

echo "chapter 2: anyone may attest; the contract recomputes FedAvg"
send "$ADMIN_KEY" \
  "attest(uint256,address[4],int64[4],int64[4],int64[4],int64[4],uint256)" \
  "$ROUND" "[$A1,$A2,$A3,$A4]" "[1,2,1,40]" "[2,2,1,40]" "[3,3,3,40]" "[4,4,5,40]" 4
need "$(call "phase(uint256)(uint8)" "$ROUND")" 2 "round attested"
AVG=$(call "avgCommitment(uint256)(uint256)" "$ROUND")
PREVIEW=$(call "previewAverage(int64[4],int64[4],int64[4],int64[4],uint256)(uint256)" "[1,2,1,40]" "[2,2,1,40]" "[3,3,3,40]" "[4,4,5,40]" 4)
need "$AVG" "$PREVIEW" "avg commitment matches preview"
need "$(call "medianScore(uint256)(uint256)" "$ROUND")" 10 "median score"
need "$(call "attestedCount(uint256)(uint256)" "$ROUND")" 4 "attested count"

echo "chapter 3: poison vote, slash, revise the average"
send "$K1" --value "$BOND" "accuse(uint256,address)" "$ROUND" "$A4"
ACC=$(call "accusationId(uint256,address)(uint256)" "$ROUND" "$A4")
need "$ACC" 1 "accusation id"
send "$K2" --value "$VOTE" "vote(uint256,bool)" "$ACC" true
cast send --private-key "$ADMIN_KEY" --rpc-url "$RPC" "$REG" "resolve(uint256)" "$ACC" >/dev/null
need "$(call "poisoned(uint256,address)(bool)" "$ROUND" "$A4")" true "outlier marked poisoned"
# Slash is 0.5 ether. Half of that (0.25 ether) is the accuser bounty; half stays in the treasury.
HALF=500000000000000000
need "$(call "stakeOf(address)(uint256)" "$A4")" "$HALF" "accused stake slashed to 0.5 ether"
QUARTER=250000000000000000
need "$(call "treasury()(uint256)")" "$QUARTER" "treasury took the other quarter"

echo "chapter 3: revise FedAvg without the poisoned update"
send "$ADMIN_KEY" \
  "revise(uint256,address[4],int64[4],int64[4],int64[4],int64[4],uint256)" \
  "$ROUND" "[$A1,$A2,$A3,0x0000000000000000000000000000000000000000]" \
  "[1,2,1,0]" "[2,2,1,0]" "[3,3,3,0]" "[4,4,5,0]" 3
need "$(call "phase(uint256)(uint8)" "$ROUND")" 3 "round settled"
REVISED=$(call "avgCommitment(uint256)(uint256)" "$ROUND")
HONEST=$(call "previewAverage(int64[4],int64[4],int64[4],int64[4],uint256)(uint256)" "[1,2,1,0]" "[2,2,1,0]" "[3,3,3,0]" "[4,4,5,0]" 3)
need "$REVISED" "$HONEST" "revised average is the honest FedAvg"
if [[ "$REVISED" == "$AVG" ]]; then
  echo "FAIL revised average did not change" >&2
  exit 1
fi
echo "ok   revised average differs from the poisoned round"
echo "anvil judge tour passed"
