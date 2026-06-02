#!/usr/bin/env bash
# Run scripts/run_swe_bench_deepseek.py N times in a row on the same instance.
#
# Usage:
#   scripts/run_swe_bench_deepseek_batch.sh [N] [INSTANCE_ID] [MODEL] [REASONING_EFFORT] [DIFFICULTY] [MAX_TOKENS]
#     N                 number of runs (default: 10)
#     INSTANCE_ID       optional; if omitted, the script picks one task per
#                       DIFFICULTY bucket each run.
#     MODEL             optional DeepSeek model id (default: deepseek-chat).
#                       Use "deepseek-v4-pro" with REASONING_EFFORT to engage the
#                       v4-pro reasoner with thinking enabled.
#     REASONING_EFFORT  optional; when set, enables DeepSeek thinking and passes
#                       this as reasoning_effort (e.g. low|medium|high|max).
#     DIFFICULTY        optional SWE-bench Verified difficulty bucket. One of:
#                       "<15 min fix", "15 min - 1 hour", "1-4 hours", ">4 hours".
#                       Only used when INSTANCE_ID is empty. Default: "<15 min fix".
#     MAX_TOKENS        optional cap on per-call output tokens. On reasoning models
#                       this covers reasoning + visible content combined; size it
#                       generously (e.g. 32768 for max, 16384 for high). When
#                       omitted, DeepSeek's server-side default applies.
#
# Per-run output goes to outputs/batch_<timestamp>/run_NN/ (predictions, traces, log).
#
# Per-run classification (failure_class):
#   resolved                 — passed SWE-bench's curated tests
#   llm_empty_patch          — agent finished cleanly but produced no diff
#   llm_patch_apply_failed   — diff malformed; git apply rejected it
#   llm_tests_failed         — patch applied but tests didn't pass
#   infra_kernel_hang        — jupyter kernel stalled; watchdog killed it
#   infra_api_error          — DeepSeek/transport error
#   infra_crash              — uncaught Python exception with no API signature
#
# Infra failures are NOT counted against the model. The run folder is deleted
# and the reason is logged to $ROOT/deleted_runs.log. Only resolved/llm_* runs
# are retained for analysis. Final tally splits resolved/kept from infra-deleted.

set -u -o pipefail
# NOTE: deliberately no `set -e` — we want to survive individual run failures.

cd "$(dirname "$0")/.."

N="${1:-10}"
INSTANCE_ID="${2:-}"
MODEL="${3:-deepseek-chat}"
REASONING_EFFORT="${4:-}"
DIFFICULTY="${5:-}"
MAX_TOKENS="${6:-}"
IDLE_TIMEOUT="${IDLE_TIMEOUT:-300}"     # seconds of zero log growth -> kill
WATCHDOG_INTERVAL=15                     # seconds between checks
ROOT="outputs/batch_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ROOT"

DELETED_LOG="$ROOT/deleted_runs.log"
: > "$DELETED_LOG"

# Run one python invocation with an idle-output watchdog.
# Writes combined stdout+stderr to $1. Returns:
#   0   normal exit
#   124 killed by watchdog (idle timeout)
#   other  python's own non-zero exit code
run_with_idle_watchdog() {
    local logfile="$1"; shift
    : > "$logfile"
    "$@" >>"$logfile" 2>&1 &
    local pid=$!

    local last_size=0 idle_since
    idle_since=$(date +%s)

    while kill -0 "$pid" 2>/dev/null; do
        sleep "$WATCHDOG_INTERVAL"
        local size now idle
        size=$(wc -c <"$logfile" 2>/dev/null || echo 0)
        now=$(date +%s)
        if (( size > last_size )); then
            last_size=$size
            idle_since=$now
        else
            idle=$((now - idle_since))
            if (( idle >= IDLE_TIMEOUT )); then
                echo "[batch] log idle ${idle}s >= ${IDLE_TIMEOUT}s, killing pid $pid" \
                    | tee -a "$logfile"
                kill -TERM "$pid" 2>/dev/null || true
                sleep 5
                if kill -0 "$pid" 2>/dev/null; then
                    kill -KILL "$pid" 2>/dev/null || true
                fi
                pkill -KILL -f "ipykernel_launcher" 2>/dev/null || true
                pkill -KILL -f "zoekt-webserver"   2>/dev/null || true
                wait "$pid" 2>/dev/null
                return 124
            fi
        fi
    done
    wait "$pid"
    return $?
}

# Decide failure_class and a human-readable reason for a finished run.
# Echoes "<class>\t<reason>" to stdout.
classify_run() {
    local logfile="$1" runrc="$2"

    if (( runrc == 124 )); then
        printf '%s\t%s\n' "infra_kernel_hang" \
            "idle-output watchdog killed run after ${IDLE_TIMEOUT}s of no log output"
        return
    fi

    # If the python script wrote its own classification, trust it.
    local fc fr
    fc=$(grep -E "^\[run\] failure_class=" "$logfile" 2>/dev/null | tail -1 \
         | sed 's/^\[run\] failure_class=//')
    if [[ -n "$fc" ]]; then
        fr=$(grep -E "^\[run\] failure_reason=" "$logfile" 2>/dev/null | tail -1 \
             | sed 's/^\[run\] failure_reason=//')
        [[ -z "$fr" ]] && fr="(no reason recorded)"
        printf '%s\t%s\n' "$fc" "$fr"
        return
    fi

    # Python died before classifying — sniff the log for API-error signatures.
    if grep -qiE "APIError|APIConnectionError|RateLimitError|APITimeoutError|Read timed out|ReadTimeout|ConnectError|Connection error|Connection reset|Service Unavailable|Too Many Requests|Bad Gateway|RemoteProtocolError|InternalServerError|\\b(429|502|503|504)\\b" "$logfile"; then
        printf '%s\t%s\n' "infra_api_error" \
            "Python crashed (exit=$runrc) with API/transport error signature in log"
        return
    fi

    if (( runrc != 0 )); then
        printf '%s\t%s\n' "infra_crash" \
            "Python exited with code $runrc; no failure_class emitted and no API signature in log"
        return
    fi

    printf '%s\t%s\n' "infra_crash" \
        "Python exited cleanly but emitted no failure_class line; treating as infra"
}

resolved=0
kept_count=0
deleted_count=0

count_resolved=0
count_llm_empty_patch=0
count_llm_patch_apply_failed=0
count_llm_tests_failed=0
count_infra_kernel_hang=0
count_infra_api_error=0
count_infra_crash=0

bump_class_count() {
    case "$1" in
        resolved)               count_resolved=$((count_resolved + 1)) ;;
        llm_empty_patch)        count_llm_empty_patch=$((count_llm_empty_patch + 1)) ;;
        llm_patch_apply_failed) count_llm_patch_apply_failed=$((count_llm_patch_apply_failed + 1)) ;;
        llm_tests_failed)       count_llm_tests_failed=$((count_llm_tests_failed + 1)) ;;
        infra_kernel_hang)      count_infra_kernel_hang=$((count_infra_kernel_hang + 1)) ;;
        infra_api_error)        count_infra_api_error=$((count_infra_api_error + 1)) ;;
        infra_crash)            count_infra_crash=$((count_infra_crash + 1)) ;;
        *)                      count_infra_crash=$((count_infra_crash + 1)) ;;
    esac
}

for i in $(seq 1 "$N"); do
    RUN_DIR="$ROOT/run_$(printf '%02d' "$i")"
    mkdir -p "$RUN_DIR/traces"
    echo
    echo "=== run $i/$N -> $RUN_DIR (idle_timeout=${IDLE_TIMEOUT}s) ==="

    args=(--output_folder "$RUN_DIR" --traces_folder "$RUN_DIR/traces" --deepseek_model "$MODEL")
    if [[ -n "$INSTANCE_ID" ]]; then
        args+=(--instance_id "$INSTANCE_ID")
    fi
    if [[ -n "$REASONING_EFFORT" ]]; then
        args+=(--reasoning_effort "$REASONING_EFFORT")
    fi
    if [[ -n "$DIFFICULTY" ]]; then
        args+=(--difficulty "$DIFFICULTY")
    fi
    if [[ -n "$MAX_TOKENS" ]]; then
        args+=(--max_tokens "$MAX_TOKENS")
    fi

    GOPATH="$HOME/go" PATH="$HOME/go/bin:$PATH" \
        run_with_idle_watchdog "$RUN_DIR/run.log" \
        .venv/bin/python scripts/run_swe_bench_deepseek.py "${args[@]}"
    rc=$?

    R=$(grep -E "^\[run\] resolved=" "$RUN_DIR/run.log" 2>/dev/null \
        | tail -1 | sed 's/.*resolved=//' || true)
    [[ -z "$R" ]] && R=0

    IFS=$'\t' read -r failure_class failure_reason < <(classify_run "$RUN_DIR/run.log" "$rc")
    bump_class_count "$failure_class"

    if [[ "$failure_class" == infra_* ]]; then
        # Salvage the log before nuking the run folder, so the deleted_runs.log
        # entry stays self-contained for postmortem.
        SALVAGE="$ROOT/deleted_run_${i}.log"
        cp "$RUN_DIR/run.log" "$SALVAGE" 2>/dev/null || true
        rm -rf "$RUN_DIR"
        deleted_count=$((deleted_count + 1))
        printf 'run %02d  class=%s\n        reason=%s\n        log=%s\n\n' \
            "$i" "$failure_class" "$failure_reason" "$SALVAGE" >> "$DELETED_LOG"
        echo "=== run $i: DELETED class=$failure_class (infra) — see $DELETED_LOG ==="
    else
        kept_count=$((kept_count + 1))
        [[ "$R" == "1" ]] && resolved=$((resolved + 1))
        cat > "$RUN_DIR/status.json" <<EOF
{"run":$i,"resolved":$R,"failure_class":"$failure_class","failure_reason":"${failure_reason//\"/\\\"}","exit":$rc}
EOF
        echo "=== run $i: class=$failure_class resolved=$R (cumulative resolved: $resolved/$kept_count kept) ==="
    fi
done

echo
echo "=========================================="
echo "Batch summary"
echo "  requested:    $N"
echo "  kept:         $kept_count"
echo "    resolved:                $count_resolved"
echo "    llm_tests_failed:        $count_llm_tests_failed"
echo "    llm_empty_patch:         $count_llm_empty_patch"
echo "    llm_patch_apply_failed:  $count_llm_patch_apply_failed"
echo "  deleted (infra):  $deleted_count"
echo "    infra_kernel_hang:       $count_infra_kernel_hang"
echo "    infra_api_error:         $count_infra_api_error"
echo "    infra_crash:             $count_infra_crash"
if (( kept_count > 0 )); then
    pct=$(awk -v r="$resolved" -v k="$kept_count" 'BEGIN { printf "%.1f", 100.0*r/k }')
    echo "  pass rate (of kept): $resolved / $kept_count = ${pct}%"
else
    echo "  pass rate: undefined (no kept runs)"
fi
echo "Root:        $ROOT"
echo "Deletion log: $DELETED_LOG"
echo "=========================================="
