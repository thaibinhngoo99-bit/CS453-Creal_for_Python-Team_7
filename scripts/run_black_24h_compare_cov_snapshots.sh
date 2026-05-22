#!/usr/bin/env bash
set -uo pipefail
trap '' HUP

result_root="${1:-results/black_24h_compare_cov_snapshots_v5}"
oracle_name="${ORACLE_NAME:-black}"
timeout_seconds="${TIMEOUT_SECONDS:-86400}"
snapshot_interval_seconds="${SNAPSHOT_INTERVAL_SECONDS:-900}"
supervisor_timeout_seconds="${SUPERVISOR_TIMEOUT_SECONDS:-$((timeout_seconds + 3600))}"
auto_target="${AUTO_TARGET:-on}"
run_variants="${RUN_VARIANTS:-from_grammar_append from_grammar_aggressive from_grammar_no_injection from_node_append from_node_aggressive from_node_no_injection}"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root" || exit 1

python_bin="${PYTHON_BIN:-$repo_root/venv/bin/python3}"
logs_dir="$result_root/logs"
mkdir -p "$logs_dir"

case "$auto_target" in
  on|true|1|yes)
    auto_target_args=()
    auto_target_label="on"
    ;;
  off|false|0|no)
    auto_target_args=(--no-auto-target)
    auto_target_label="off"
    ;;
  *)
    echo "AUTO_TARGET must be one of: on, off, true, false, 1, 0, yes, no" >&2
    exit 2
    ;;
esac

{
  printf 'oracle_name=%s\n' "$oracle_name"
  printf 'timeout_seconds=%s\n' "$timeout_seconds"
  printf 'snapshot_interval_seconds=%s\n' "$snapshot_interval_seconds"
  printf 'supervisor_timeout_seconds=%s\n' "$supervisor_timeout_seconds"
  printf 'auto_target=%s\n' "$auto_target_label"
  printf 'run_variants=%s\n' "$run_variants"
} > "$result_root/experiment_config.txt"

run_variant() {
  local name="$1"
  shift

  {
    printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
    printf 'supervisor_timeout_seconds=%s\n' "$supervisor_timeout_seconds"
    printf 'auto_target=%s\n' "$auto_target_label"
    printf 'command=%q' "$python_bin"
    printf ' %q' -u src/execute_proposed.py "$@"
    printf '\n'
  } > "$logs_dir/$name.meta.log"

  if command -v timeout >/dev/null 2>&1; then
    timeout --verbose --signal=INT --kill-after=300 "$supervisor_timeout_seconds" \
      "$python_bin" -u src/execute_proposed.py "$@" \
      > "$logs_dir/$name.stdout.log" \
      2> "$logs_dir/$name.stderr.log"
  else
    "$python_bin" -u src/execute_proposed.py "$@" \
      > "$logs_dir/$name.stdout.log" \
      2> "$logs_dir/$name.stderr.log"
  fi
  local status=$?

  {
    printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
    printf 'exit_status=%s\n' "$status"
  } >> "$logs_dir/$name.meta.log"
  return "$status"
}

common_args=(
  --oracle "$oracle_name"
  --timeout "$timeout_seconds"
  --coverage
  --coverage-snapshot-interval "$snapshot_interval_seconds"
  "${auto_target_args[@]}"
)

start_variant() {
  local variant="$1"

  case "$variant" in
    from_grammar_append)
      run_variant "$variant" \
        "${common_args[@]}" \
        --generation-mode from_grammar \
        --injection-strategy append \
        --results-dir "$result_root/$variant" &
      ;;
    from_grammar_aggressive)
      run_variant "$variant" \
        "${common_args[@]}" \
        --generation-mode from_grammar \
        --injection-strategy aggressive \
        --results-dir "$result_root/$variant" &
      ;;
    from_grammar_no_injection)
      run_variant "$variant" \
        "${common_args[@]}" \
        --generation-mode from_grammar \
        --no-injection \
        --results-dir "$result_root/$variant" &
      ;;
    from_node_append)
      run_variant "$variant" \
        "${common_args[@]}" \
        --generation-mode from_node \
        --injection-strategy append \
        --results-dir "$result_root/$variant" &
      ;;
    from_node_aggressive)
      run_variant "$variant" \
        "${common_args[@]}" \
        --generation-mode from_node \
        --injection-strategy aggressive \
        --results-dir "$result_root/$variant" &
      ;;
    from_node_no_injection)
      run_variant "$variant" \
        "${common_args[@]}" \
        --generation-mode from_node \
        --no-injection \
        --results-dir "$result_root/$variant" &
      ;;
    *)
      echo "unknown variant: $variant" >&2
      return 2
      ;;
  esac
}

pids=()
read -r -a variants <<< "${run_variants//,/ }"
for variant in "${variants[@]}"; do
  start_variant "$variant"
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done

exit "$status"
