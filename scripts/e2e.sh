#!/usr/bin/env bash
# Tour driver for Checkable Coordinator (Fe federated-learning registry).
#
# This is the script a judge (or Kent) runs. It does not train a model. It
# builds the Fe ingot, runs the in-EVM tests chapter by chapter, then deploys
# the same contract to a local Anvil node and repeats the story with four
# accounts. The last stage is teardown: it confirms the local Anvil is gone
# and removes leftover pid or temp files, and it does not delete tour logs.
#
# Each stage is a separate process: its own log, its own pass/fail, its own
# timing. A failure in one stage does not stop the later stages. The script
# exits 0 only when every stage passed.
#
# Usage:
#   ./scripts/e2e.sh           interactive menu (or run-all if stdin is not a tty)
#   ./scripts/e2e.sh --ci      run every stage, no prompts
#   ./scripts/e2e.sh --all     same as --ci
#   ./scripts/e2e.sh --stage N run one stage (1..8)
#   ./scripts/e2e.sh --help
#
# Stages:
#   1  toolchain    `fe --version` must report 26.5.0
#   2  build        `fe build`
#   3  unit         pure FedAvg, hash, and slash tests
#   4  chapter 1    register, open round, submit receipts
#   5  chapter 2    aggregator-free FedAvg attestation
#   6  chapter 3    poison vote, slash, revise
#   7  tour         full in-EVM story plus the Anvil deployment
#   8  teardown     last step: stop leftover Anvil, remove pid/temp files,
#                   keep logs/e2e-* for this run

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.fe/bin:${HOME}/.foundry/bin:${PATH}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="${ROOT}/logs/e2e-${STAMP}"
mkdir -p "$LOG_DIR"

FAILURES=0
declare -a SUMMARY=()

now_s() {
  python3 -c 'import time; print(f"{time.time():.6f}")'
}

# Run one stage in a subshell so a failing command cannot abort the tour.
# Arguments: id, title, function-name
run_stage() {
  local id="$1"
  local title="$2"
  local fn="$3"
  local log="${LOG_DIR}/${id}.log"
  local start end elapsed code
  start="$(now_s)"
  # set -e inside the subshell so the first failing command fails the stage.
  # The parent keeps going and records the exit code.
  (
    set -euo pipefail
    "$fn"
  ) >"$log" 2>&1
  code=$?
  end="$(now_s)"
  elapsed="$(python3 -c "print(f'{${end} - ${start}:.2f}')")"
  local result="PASS"
  if [[ "$code" -ne 0 ]]; then
    result="FAIL"
    FAILURES=$((FAILURES + 1))
  fi
  SUMMARY+=("$(printf '%-10s  %-8s  %7ss  %s' "$id" "$result" "$elapsed" "$title")")
  if [[ "$result" == "PASS" ]]; then
    printf 'PASS  %-10s  %7ss  %s\n' "$id" "$elapsed" "$title"
  else
    printf 'FAIL  %-10s  %7ss  %s\n' "$id" "$elapsed" "$title"
    echo "      log: ${log}"
    echo "      --- tail ---"
    tail -n 25 "$log" | sed 's/^/      /'
    echo "      --- end ---"
  fi
}

stage_toolchain() {
  command -v fe
  local ver
  ver="$(fe --version)"
  echo "$ver"
  case "$ver" in
    *"26.5.0"*) ;;
    *)
      echo "expected Fe 26.5.0, found: $ver"
      return 1
      ;;
  esac
  if command -v cast >/dev/null && command -v anvil >/dev/null; then
    cast --version
    anvil --version
  else
    echo "foundry is not installed; the anvil stage will fail"
    return 1
  fi
}

stage_build() {
  fe build --out-dir out
  test -s out/FlRegistry.bin
  test -s out/FlRegistry.abi.json
}

stage_unit() {
  fe test --jobs 1 --filter test_unit
}

stage_chapter1() {
  fe test --jobs 1 --filter test_stage1
}

stage_chapter2() {
  fe test --jobs 1 --filter test_stage2
}

stage_chapter3() {
  fe test --jobs 1 --filter test_stage3
}

stage_tour() {
  fe test --jobs 1 --filter test_tour
  ./scripts/anvil_tour.sh
}

# True if something accepts a TCP connection on 127.0.0.1:$1.
_port_in_use() {
  python3 - "$1" <<'PORTCHECK'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.3)
try:
    r = s.connect_ex(("127.0.0.1", port))
finally:
    s.close()
sys.exit(0 if r == 0 else 1)
PORTCHECK
}

# Stop a leftover Anvil we started for this tour. No-op if nothing is running.
# Never deletes logs/e2e-* (including the current run). Never kills a node the
# caller asked us to reuse via ANVIL_RPC.
stage_teardown() {
  local port="${ANVIL_PORT:-18545}"
  local pidfile="${ROOT}/.anvil.pid"
  local tmp_log="/tmp/fl-anvil.log"
  local pid cmd leftover

  echo "teardown: checking port ${port} and pidfile ${pidfile}"
  echo "logs for this run stay in ${LOG_DIR} (not deleted)"

  if [[ -n "${ANVIL_RPC:-}" ]]; then
    echo "ANVIL_RPC=${ANVIL_RPC}; not stopping a reused node"
  fi

  if [[ -f "$pidfile" ]]; then
    pid="$(tr -d '[:space:]' < "$pidfile" || true)"
    echo "found pidfile, pid='${pid}'"
    if [[ -n "$pid" && "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
      cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
      echo "process still running: ${cmd}"
      if [[ -z "${ANVIL_RPC:-}" ]]; then
        kill "$pid" 2>/dev/null || true
        sleep 0.2
        if kill -0 "$pid" 2>/dev/null; then
          echo "escalating to SIGKILL on ${pid}"
          kill -9 "$pid" 2>/dev/null || true
          sleep 0.1
        fi
      else
        echo "leaving reused node pid ${pid} alone"
      fi
    else
      echo "pidfile is stale (process not running)"
    fi
    rm -f "$pidfile"
    echo "removed ${pidfile}"
  else
    echo "no pidfile (anvil_tour usually removes it on exit)"
  fi

  if [[ -z "${ANVIL_RPC:-}" ]]; then
    leftover="$(pgrep -af "anvil --host 127.0.0.1 --port ${port}" 2>/dev/null || true)"
    if [[ -n "$leftover" ]]; then
      echo "leftover anvil still running:"
      echo "$leftover"
      while read -r lp rest; do
        [[ -z "${lp:-}" ]] && continue
        [[ "$lp" =~ ^[0-9]+$ ]] || continue
        echo "stopping leftover anvil pid ${lp}"
        kill "$lp" 2>/dev/null || true
        sleep 0.2
        if kill -0 "$lp" 2>/dev/null; then
          kill -9 "$lp" 2>/dev/null || true
          sleep 0.1
        fi
      done <<< "$leftover"
    else
      echo "no leftover anvil process on port ${port}"
    fi
  fi

  if [[ -f "$tmp_log" ]]; then
    rm -f "$tmp_log"
    echo "removed ${tmp_log}"
  else
    echo "no ${tmp_log}"
  fi

  if [[ -f "$pidfile" ]]; then
    echo "FAIL: ${pidfile} still exists"
    return 1
  fi

  if [[ -z "${ANVIL_RPC:-}" ]] && _port_in_use "$port"; then
    echo "FAIL: something still listens on 127.0.0.1:${port}"
    return 1
  fi
  if [[ -z "${ANVIL_RPC:-}" ]]; then
    echo "port ${port} is free"
  fi

  if [[ ! -d "$LOG_DIR" ]]; then
    echo "FAIL: current log dir ${LOG_DIR} is missing"
    return 1
  fi
  echo "current run logs still in ${LOG_DIR}"
  echo "teardown clean"
}

print_summary() {
  echo
  echo "Checkable Coordinator summary  (logs in ${LOG_DIR})"
  echo "ID          RESULT      TIME  TITLE"
  local line
  for line in "${SUMMARY[@]}"; do
    echo "$line"
  done
  echo
  if [[ "$FAILURES" -eq 0 ]]; then
    echo "PASS  ${#SUMMARY[@]} stages, 0 failed"
    return 0
  fi
  echo "FAIL  ${FAILURES} stage(s) failed"
  return 1
}

reset_results() {
  FAILURES=0
  SUMMARY=()
}

run_all() {
  reset_results
  echo "Checkable Coordinator  repo ${ROOT}"
  echo "logs                ${LOG_DIR}"
  echo
  run_stage toolchain "Fe 26.5.0 and Foundry on PATH" stage_toolchain
  run_stage build "fe build --out-dir out" stage_build
  run_stage unit "pure FedAvg, hash, and slash tests" stage_unit
  run_stage chapter1 "register, open round, submit receipts" stage_chapter1
  run_stage chapter2 "FedAvg attestation" stage_chapter2
  run_stage chapter3 "poison vote, slash, revise" stage_chapter3
  run_stage tour "in-EVM tour plus Anvil deployment" stage_tour
  run_stage teardown "stop leftover Anvil; keep logs" stage_teardown
  print_summary
}

run_one() {
  reset_results
  case "$1" in
    1) run_stage toolchain "Fe 26.5.0 and Foundry on PATH" stage_toolchain ;;
    2) run_stage build "fe build --out-dir out" stage_build ;;
    3) run_stage unit "pure FedAvg, hash, and slash tests" stage_unit ;;
    4) run_stage chapter1 "register, open round, submit receipts" stage_chapter1 ;;
    5) run_stage chapter2 "FedAvg attestation" stage_chapter2 ;;
    6) run_stage chapter3 "poison vote, slash, revise" stage_chapter3 ;;
    7) run_stage tour "in-EVM tour plus Anvil deployment" stage_tour ;;
    8) run_stage teardown "stop leftover Anvil; keep logs" stage_teardown ;;
    *)
      echo "unknown stage: $1" >&2
      return 2
      ;;
  esac
  print_summary
}

usage() {
  cat <<'EOF'
Usage: ./scripts/e2e.sh [--ci | --all | --stage N | --help]

  (no args, terminal)   menu
  (no args, no tty)     run every stage
  --ci, --all           run every stage, ending with teardown
  --stage N             run stage N only (1 toolchain, 2 build, 3 unit,
                        4 chapter 1, 5 chapter 2, 6 chapter 3, 7 full tour,
                        8 teardown)

Exit 0 only when every requested stage passes.
EOF
}

menu() {
  while true; do
    cat <<'EOF'

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
EOF
    printf 'choice> '
    local choice
    if ! read -r choice; then
      echo
      return 0
    fi
    case "$choice" in
      1|2|3|4|5|6|7|8) run_one "$choice" ;;
      9|a|all) run_all ;;
      q|Q) return 0 ;;
      *) echo "enter 1-9 or q" ;;
    esac
  done
}

case "${1:-}" in
  --help|-h) usage; exit 0 ;;
  --ci|--all) run_all; exit $? ;;
  --stage)
    if [[ -z "${2:-}" ]]; then
      usage
      exit 2
    fi
    run_one "$2"
    exit $?
    ;;
  "")
    if [[ -t 0 ]]; then
      menu
      exit $?
    fi
    run_all
    exit $?
    ;;
  *)
    usage
    exit 2
    ;;
esac
