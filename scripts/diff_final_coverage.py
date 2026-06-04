#!/usr/bin/env python3
"""Create human-inspectable final coverage diffs across strategy variants."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


VARIANTS = ("aggressive", "append", "no_injection")
VARIANT_LABEL = {
    "aggressive": "aggressive",
    "append": "append",
    "no_injection": "no injection",
}
PYTHON_TARGETS = {
    "black": Path("results/black_from_node_24h_auto_target_on_cst_lazy_batch10000_v1"),
    "tokenize": Path("results/tokenize_from_node_24h_auto_target_on_cst_lazy_batch10000_v1"),
    "lib2to3": Path("results/lib2to3_from_node_24h_auto_target_on_cst_lazy_batch10000_v1"),
}
LIBCST_NATIVE_ROOT = Path(
    ".native_coverage/reports/"
    "libcst_native_from_node_24h_auto_target_on_cst_lazy_batch10000_snapshots_v1"
)
OUT_DIR = Path("results/coverage_diffs")


@dataclass(frozen=True)
class PyCoverage:
    target: str
    variant: str
    path: Path
    data: dict


def pct(value: float) -> str:
    return f"{value:.2f}%"


def yn(value: bool) -> str:
    return "yes" if value else "no"


def md_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def read_source_line(file_name: str, line_no: int) -> str:
    path = Path(file_name)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, start=1):
                if idx == line_no:
                    return line.rstrip()
    except OSError:
        return ""
    return ""


def line_range(values: set[int]) -> str:
    if not values:
        return "-"
    ordered = sorted(values)
    ranges: list[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(ranges)


def load_python_coverages() -> dict[str, dict[str, PyCoverage]]:
    loaded: dict[str, dict[str, PyCoverage]] = {}
    for target, root in PYTHON_TARGETS.items():
        loaded[target] = {}
        for variant in VARIANTS:
            path = root / variant / target / "coverage.json"
            loaded[target][variant] = PyCoverage(
                target=target,
                variant=variant,
                path=path,
                data=json.loads(path.read_text()),
            )
    return loaded


def python_file_names(coverages: dict[str, PyCoverage]) -> list[str]:
    names: set[str] = set()
    for cov in coverages.values():
        names.update(cov.data["files"])
    return sorted(names)


def executed_lines(cov: PyCoverage, file_name: str) -> set[int]:
    return set(cov.data["files"].get(file_name, {}).get("executed_lines", []))


def executed_branches(cov: PyCoverage, file_name: str) -> set[tuple[int, int]]:
    return {
        tuple(branch)
        for branch in cov.data["files"].get(file_name, {}).get("executed_branches", [])
    }


def write_python_csvs(all_cov: dict[str, dict[str, PyCoverage]]) -> None:
    line_rows: list[list[object]] = []
    branch_rows: list[list[object]] = []
    for target, coverages in all_cov.items():
        for file_name in python_file_names(coverages):
            line_sets = {
                variant: executed_lines(cov, file_name)
                for variant, cov in coverages.items()
            }
            all_lines = sorted(set().union(*line_sets.values()))
            for line_no in all_lines:
                flags = {variant: line_no in line_sets[variant] for variant in VARIANTS}
                if len(set(flags.values())) <= 1:
                    continue
                line_rows.append(
                    [
                        target,
                        file_name,
                        line_no,
                        *[yn(flags[variant]) for variant in VARIANTS],
                        read_source_line(file_name, line_no),
                    ]
                )

            branch_sets = {
                variant: executed_branches(cov, file_name)
                for variant, cov in coverages.items()
            }
            all_branches = sorted(set().union(*branch_sets.values()))
            for from_line, to_line in all_branches:
                flags = {
                    variant: (from_line, to_line) in branch_sets[variant]
                    for variant in VARIANTS
                }
                if len(set(flags.values())) <= 1:
                    continue
                branch_rows.append(
                    [
                        target,
                        file_name,
                        from_line,
                        to_line,
                        *[yn(flags[variant]) for variant in VARIANTS],
                        read_source_line(file_name, from_line),
                    ]
                )

    with (OUT_DIR / "python_line_diffs.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "target",
                "file",
                "line",
                "aggressive",
                "append",
                "no_injection",
                "source",
            ]
        )
        writer.writerows(line_rows)

    with (OUT_DIR / "python_branch_diffs.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "target",
                "file",
                "from_line",
                "to_line",
                "aggressive",
                "append",
                "no_injection",
                "source_from_line",
            ]
        )
        writer.writerows(branch_rows)


def python_totals_table(coverages: dict[str, PyCoverage]) -> list[str]:
    lines = [
        "| Strategy | Total | Statements | Branches | Covered Lines | Covered Branches |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        totals = coverages[variant].data["totals"]
        lines.append(
            "| "
            + " | ".join(
                [
                    VARIANT_LABEL[variant],
                    pct(float(totals["percent_covered"])),
                    pct(float(totals["percent_statements_covered"])),
                    pct(float(totals["percent_branches_covered"])),
                    f"{totals['covered_lines']} / {totals['num_statements']}",
                    f"{totals['covered_branches']} / {totals['num_branches']}",
                ]
            )
            + " |"
        )
    return lines


def python_pairwise_table(coverages: dict[str, PyCoverage]) -> list[str]:
    pairs = (
        ("append", "aggressive"),
        ("append", "no_injection"),
        ("aggressive", "no_injection"),
    )
    lines = [
        "| Comparison | Extra Lines | Missing Lines | Extra Branches | Missing Branches |",
        "|---|---:|---:|---:|---:|",
    ]
    all_files = python_file_names(coverages)
    for left, right in pairs:
        extra_lines = missing_lines = extra_branches = missing_branches = 0
        for file_name in all_files:
            left_lines = executed_lines(coverages[left], file_name)
            right_lines = executed_lines(coverages[right], file_name)
            left_branches = executed_branches(coverages[left], file_name)
            right_branches = executed_branches(coverages[right], file_name)
            extra_lines += len(left_lines - right_lines)
            missing_lines += len(right_lines - left_lines)
            extra_branches += len(left_branches - right_branches)
            missing_branches += len(right_branches - left_branches)
        lines.append(
            f"| {VARIANT_LABEL[left]} vs {VARIANT_LABEL[right]} | "
            f"{extra_lines} | {missing_lines} | {extra_branches} | {missing_branches} |"
        )
    return lines


def python_file_diff_rows(coverages: dict[str, PyCoverage]) -> list[tuple]:
    rows: list[tuple] = []
    for file_name in python_file_names(coverages):
        sets = {variant: executed_lines(coverages[variant], file_name) for variant in VARIANTS}
        union = set().union(*sets.values())
        intersection = set.intersection(*sets.values()) if all(sets.values()) else set()
        differing = {
            line
            for line in union
            if len({line in sets[variant] for variant in VARIANTS}) > 1
        }
        if not differing:
            continue
        only = {
            variant: sets[variant] - set().union(
                *(sets[other] for other in VARIANTS if other != variant)
            )
            for variant in VARIANTS
        }
        rows.append(
            (
                len(differing),
                file_name,
                len(union),
                len(intersection),
                len(only["aggressive"]),
                len(only["append"]),
                len(only["no_injection"]),
                line_range(only["aggressive"]),
                line_range(only["append"]),
                line_range(only["no_injection"]),
            )
        )
    return sorted(rows, reverse=True)


def python_target_report(target: str, coverages: dict[str, PyCoverage]) -> str:
    lines = [f"# {target} Final Coverage Diff", ""]
    lines.extend(python_totals_table(coverages))
    lines.extend(["", "## Pairwise Coverage Set Deltas", ""])
    lines.extend(python_pairwise_table(coverages))
    lines.extend(
        [
            "",
            "## Files With Differing Covered Lines",
            "",
            "The range columns show lines covered only by that one strategy, not by either of the other two.",
            "",
            "| File | Differing Lines | Covered By Any | Covered By All | Only Aggressive | Only Append | Only No Injection | Aggressive-Only Ranges | Append-Only Ranges | No-Injection-Only Ranges |",
            "|---|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for (
        differing,
        file_name,
        union_count,
        intersection_count,
        only_aggressive,
        only_append,
        only_no_injection,
        aggressive_ranges,
        append_ranges,
        no_injection_ranges,
    ) in python_file_diff_rows(coverages):
        lines.append(
            "| "
            + " | ".join(
                md_escape(value)
                for value in [
                    file_name,
                    differing,
                    union_count,
                    intersection_count,
                    only_aggressive,
                    only_append,
                    only_no_injection,
                    aggressive_ranges,
                    append_ranges,
                    no_injection_ranges,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Full line-level and branch-level rows are in `python_line_diffs.csv` and `python_branch_diffs.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


NATIVE_ROW_RE = re.compile(
    r"^(?P<file>\S.*?)\s+"
    r"(?P<regions>\d+)\s+(?P<missed_regions>\d+)\s+(?P<region_pct>[\d.]+)%\s+"
    r"(?P<functions>\d+)\s+(?P<missed_functions>\d+)\s+(?P<function_pct>[\d.]+)%\s+"
    r"(?P<lines>\d+)\s+(?P<missed_lines>\d+)\s+(?P<line_pct>[\d.]+)%\s+"
    r"(?P<branches>\d+)\s+(?P<missed_branches>\d+)\s+(?P<branch_pct>[\d.]+%|-)$"
)


def latest_native_report(variant: str) -> Path:
    reports = sorted((LIBCST_NATIVE_ROOT / variant / "snapshots").glob("snapshot_*.txt"))
    if not reports:
        raise FileNotFoundError(f"No native reports for {variant}")
    return reports[-1]


def read_native_report(path: Path) -> dict[str, dict[str, float | int | str]]:
    rows: dict[str, dict[str, float | int | str]] = {}
    for line in path.read_text(errors="replace").splitlines():
        match = NATIVE_ROW_RE.match(line)
        if not match:
            continue
        data = match.groupdict()
        file_name = data.pop("file")
        rows[file_name] = {
            "regions": int(data["regions"]),
            "missed_regions": int(data["missed_regions"]),
            "region_pct": float(data["region_pct"]),
            "functions": int(data["functions"]),
            "missed_functions": int(data["missed_functions"]),
            "function_pct": float(data["function_pct"]),
            "lines": int(data["lines"]),
            "missed_lines": int(data["missed_lines"]),
            "line_pct": float(data["line_pct"]),
            "branches": int(data["branches"]),
            "missed_branches": int(data["missed_branches"]),
            "branch_pct": data["branch_pct"],
        }
    return rows


def write_libcst_csv(native: dict[str, dict[str, dict[str, float | int | str]]]) -> None:
    files = sorted(set().union(*(set(rows) for rows in native.values())))
    with (OUT_DIR / "libcst_native_file_diffs.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "file",
                "aggressive_line_pct",
                "append_line_pct",
                "no_injection_line_pct",
                "append_minus_aggressive_line_pct",
                "append_minus_no_injection_line_pct",
                "aggressive_minus_no_injection_line_pct",
                "aggressive_region_pct",
                "append_region_pct",
                "no_injection_region_pct",
                "aggressive_function_pct",
                "append_function_pct",
                "no_injection_function_pct",
            ]
        )
        for file_name in files:
            values = {
                variant: native[variant].get(file_name, {})
                for variant in VARIANTS
            }
            line_pct = {
                variant: float(values[variant].get("line_pct", 0.0))
                for variant in VARIANTS
            }
            writer.writerow(
                [
                    file_name,
                    line_pct["aggressive"],
                    line_pct["append"],
                    line_pct["no_injection"],
                    line_pct["append"] - line_pct["aggressive"],
                    line_pct["append"] - line_pct["no_injection"],
                    line_pct["aggressive"] - line_pct["no_injection"],
                    values["aggressive"].get("region_pct", ""),
                    values["append"].get("region_pct", ""),
                    values["no_injection"].get("region_pct", ""),
                    values["aggressive"].get("function_pct", ""),
                    values["append"].get("function_pct", ""),
                    values["no_injection"].get("function_pct", ""),
                ]
            )


def libcst_report(native: dict[str, dict[str, dict[str, float | int | str]]]) -> str:
    lines = ["# libcst Native Final Coverage Diff", ""]
    lines.append(
        "LibCST uses LLVM native coverage here. This report compares per-Rust-file "
        "line, region, and function coverage from the final native snapshots."
    )
    lines.extend(["", "## Totals", ""])
    lines.extend(
        [
            "| Strategy | Line | Region | Function | Snapshot |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for variant in VARIANTS:
        total = native[variant]["TOTAL"]
        lines.append(
            f"| {VARIANT_LABEL[variant]} | {pct(float(total['line_pct']))} | "
            f"{pct(float(total['region_pct']))} | {pct(float(total['function_pct']))} | "
            f"{latest_native_report(variant).name} |"
        )

    files = sorted(set().union(*(set(rows) for rows in native.values())) - {"TOTAL"})
    delta_rows = []
    for file_name in files:
        line_pct = {
            variant: float(native[variant].get(file_name, {}).get("line_pct", 0.0))
            for variant in VARIANTS
        }
        spread = max(line_pct.values()) - min(line_pct.values())
        if spread <= 0:
            continue
        delta_rows.append((spread, file_name, line_pct))
    delta_rows.sort(reverse=True)

    lines.extend(
        [
            "",
            "## Files With Differing Native Line Coverage",
            "",
            "| File | Aggressive | Append | No Injection | Spread | Append - Aggressive | Append - No Injection | Aggressive - No Injection |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for spread, file_name, line_pct in delta_rows:
        lines.append(
            f"| {md_escape(file_name)} | {pct(line_pct['aggressive'])} | "
            f"{pct(line_pct['append'])} | {pct(line_pct['no_injection'])} | "
            f"{spread:.2f} pts | {line_pct['append'] - line_pct['aggressive']:+.2f} pts | "
            f"{line_pct['append'] - line_pct['no_injection']:+.2f} pts | "
            f"{line_pct['aggressive'] - line_pct['no_injection']:+.2f} pts |"
        )
    lines.extend(["", "Full per-file native rows are in `libcst_native_file_diffs.csv`.", ""])
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_cov = load_python_coverages()
    write_python_csvs(all_cov)

    report_parts = [
        "# Final Strategy Coverage Diffs",
        "",
        "Source runs: 24h `from_node`, auto-target on, batch 10000.",
        "",
        "Python targets compare final `coverage.py` line and branch sets. "
        "LibCST compares final LLVM native per-file coverage.",
        "",
    ]

    for target, coverages in all_cov.items():
        target_report = python_target_report(target, coverages)
        (OUT_DIR / f"{target}_final_coverage_diff.md").write_text(target_report + "\n")
        report_parts.append(target_report)
        report_parts.append("")

    native = {
        variant: read_native_report(latest_native_report(variant))
        for variant in VARIANTS
    }
    write_libcst_csv(native)
    native_report = libcst_report(native)
    (OUT_DIR / "libcst_native_final_coverage_diff.md").write_text(native_report + "\n")
    report_parts.append(native_report)
    report_parts.append("")

    (OUT_DIR / "final_strategy_coverage_diff.md").write_text("\n".join(report_parts))
    print(f"Wrote {OUT_DIR / 'final_strategy_coverage_diff.md'}")
    print(f"Wrote {OUT_DIR / 'python_line_diffs.csv'}")
    print(f"Wrote {OUT_DIR / 'python_branch_diffs.csv'}")
    print(f"Wrote {OUT_DIR / 'libcst_native_file_diffs.csv'}")


if __name__ == "__main__":
    main()
