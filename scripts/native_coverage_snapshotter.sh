#!/usr/bin/env bash

set -u

if [ "$#" -ne 8 ]; then
  echo "usage: $0 VARIANT PARENT_PID PROFILE_DIR REPORT_DIR RESULT_DIR NATIVE_SO INTERVAL_SECONDS FIRST_DELAY_SECONDS" >&2
  exit 2
fi

variant="$1"
parent_pid="$2"
profile_dir="$3"
report_dir="$4"
result_dir="$5"
native_so="$6"
interval_seconds="$7"
first_delay_seconds="$8"

snapshots_dir="$report_dir/snapshots"
manifest="$snapshots_dir/manifest.tsv"
errors="$snapshots_dir/errors.log"

mkdir -p "$snapshots_dir"
printf "snapshot\telapsed_seconds\ttotal_programs\ttext_path\tprofdata_path\terror\n" > "$manifest"
: > "$errors"

start_epoch=$(date +%s)
snapshot_index=0

sleep "$first_delay_seconds"

write_snapshot() {
  local elapsed stem text_path profdata_path total_programs
  elapsed=$(( $(date +%s) - start_epoch ))
  stem=$(printf "snapshot_%04d_%06ds" "$snapshot_index" "$elapsed")
  text_path="$snapshots_dir/$stem.txt"
  profdata_path="$snapshots_dir/$stem.profdata"
  total_programs=0

  if [ -f "$result_dir/libcst/execution_results.txt" ]; then
    total_programs=$(wc -l < "$result_dir/libcst/execution_results.txt")
  fi

  if ! compgen -G "$profile_dir/*.profraw" >/dev/null; then
    printf "%s\t%s\t%s\t%s\t%s\tno_profraw\n" \
      "$snapshot_index" "$elapsed" "$total_programs" "$text_path" "$profdata_path" >> "$manifest"
    snapshot_index=$((snapshot_index + 1))
    return
  fi

  if llvm-profdata-17 merge -sparse "$profile_dir"/*.profraw -o "$profdata_path" 2>> "$errors" \
    && llvm-cov-17 report "$native_so" \
      -instr-profile="$profdata_path" \
      -ignore-filename-regex='/(\.cargo/registry|build/rustc-)' \
      > "$text_path" 2>> "$errors"; then
    printf "%s\t%s\t%s\t%s\t%s\t\n" \
      "$snapshot_index" "$elapsed" "$total_programs" "$text_path" "$profdata_path" >> "$manifest"
  else
    printf "%s\t%s\t%s\t%s\t%s\treport_failed\n" \
      "$snapshot_index" "$elapsed" "$total_programs" "$text_path" "$profdata_path" >> "$manifest"
  fi

  snapshot_index=$((snapshot_index + 1))
}

while kill -0 "$parent_pid" 2>/dev/null; do
  write_snapshot
  sleep "$interval_seconds"
done

write_snapshot
