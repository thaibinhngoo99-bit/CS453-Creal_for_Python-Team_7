#!/usr/bin/env python3
"""Generate gcov-style source snippets for final strategy coverage diffs."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


VARIANTS = ("aggressive", "append", "no_injection")
LABELS = {
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
LIBCST_OBJECT = Path(
    "venv_libcst_native_snap/lib/python3.12/site-packages/"
    "libcst/native.cpython-312-x86_64-linux-gnu.so"
)
LIBCST_SOURCE_MARKER = "/.native_coverage/src/libcst-1.8.6/native/libcst/src/"
OUT_DIR = Path("results/coverage_source_diffs")


@dataclass(frozen=True)
class PyVariantCoverage:
    target: str
    variant: str
    data: dict

    @property
    def total_pct(self) -> float:
        return float(self.data["totals"]["percent_covered"])

    @property
    def covered_lines(self) -> int:
        return int(self.data["totals"]["covered_lines"])


def md_escape(value: object) -> str:
    return str(value).replace("|", "\\|")


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def line_ranges(values: set[int]) -> str:
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


def clusters(values: set[int], context: int = 2) -> list[tuple[int, int]]:
    if not values:
        return []
    grouped: list[tuple[int, int]] = []
    ordered = sorted(values)
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value <= previous + context * 2 + 1:
            previous = value
            continue
        grouped.append((max(1, start - context), previous + context))
        start = previous = value
    grouped.append((max(1, start - context), previous + context))
    return grouped


def load_python_target(target: str, root: Path) -> dict[str, PyVariantCoverage]:
    return {
        variant: PyVariantCoverage(
            target=target,
            variant=variant,
            data=json.loads((root / variant / target / "coverage.json").read_text()),
        )
        for variant in VARIANTS
    }


def py_file_names(coverages: dict[str, PyVariantCoverage]) -> list[str]:
    names: set[str] = set()
    for cov in coverages.values():
        names.update(cov.data["files"])
    return sorted(names)


def py_executed_lines(cov: PyVariantCoverage, file_name: str) -> set[int]:
    return set(cov.data["files"].get(file_name, {}).get("executed_lines", []))


def strategy_order_python(coverages: dict[str, PyVariantCoverage]) -> list[str]:
    return sorted(
        VARIANTS,
        key=lambda variant: (
            coverages[variant].total_pct,
            coverages[variant].covered_lines,
        ),
        reverse=True,
    )


def pairwise_better_worse(order: list[str], score) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for i, better in enumerate(order):
        for worse in order[i + 1 :]:
            if score(better) > score(worse):
                pairs.append((better, worse))
    return pairs


def render_python_comparison(
    target: str,
    coverages: dict[str, PyVariantCoverage],
    better: str,
    worse: str,
) -> str:
    lines = [
        f"# {target}: {LABELS[better]} only vs {LABELS[worse]}",
        "",
        f"`{LABELS[better]}` final coverage: {coverages[better].total_pct:.2f}%",
        f"`{LABELS[worse]}` final coverage: {coverages[worse].total_pct:.2f}%",
        "",
        "Lines marked `+` were executed by the better strategy and not executed by the worse strategy.",
        "Context lines are included with `|`; lines executed only by the worse strategy, if adjacent, are marked `-`.",
        "",
    ]

    total_extra = 0
    file_sections: list[str] = []
    for file_name in py_file_names(coverages):
        better_set = py_executed_lines(coverages[better], file_name)
        worse_set = py_executed_lines(coverages[worse], file_name)
        better_only = better_set - worse_set
        if not better_only:
            continue
        total_extra += len(better_only)
        source_path = Path(file_name)
        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path
        source = read_lines(source_path)
        section = [
            f"## {file_name}",
            "",
            f"Better-only lines: {len(better_only)}",
            f"Ranges: `{line_ranges(better_only)}`",
            "",
            "```text",
        ]
        for start, end in clusters(better_only):
            section.append(f"@@ {start}-{min(end, len(source) or end)} @@")
            for line_no in range(start, end + 1):
                text = source[line_no - 1] if 1 <= line_no <= len(source) else ""
                if line_no in better_only:
                    marker = "+"
                elif line_no in worse_set - better_set:
                    marker = "-"
                else:
                    marker = "|"
                better_flag = "hit" if line_no in better_set else "miss"
                worse_flag = "hit" if line_no in worse_set else "miss"
                section.append(
                    f"{marker} {line_no:5d}  better:{better_flag:<4} worse:{worse_flag:<4}  {text}"
                )
            section.append("")
        section.append("```")
        section.append("")
        file_sections.append("\n".join(section))

    lines.append(f"Total better-only executed lines: **{total_extra}**")
    lines.append("")
    lines.extend(file_sections)
    return "\n".join(lines)


SHOW_RE = re.compile(r"^\s*(?P<line>\d+)\|(?P<count>[^|]*)\|(?P<source>.*)$")


def latest_profdata(variant: str) -> Path:
    matches = sorted((LIBCST_NATIVE_ROOT / variant / "snapshots").glob("snapshot_*.profdata"))
    if not matches:
        raise FileNotFoundError(f"No profdata for {variant}")
    return matches[-1]


def llvm_export_files(profdata: Path) -> list[str]:
    output = subprocess.check_output(
        [
            "llvm-cov-17",
            "export",
            str(LIBCST_OBJECT),
            f"-instr-profile={profdata}",
            "-format=text",
        ],
        text=True,
    )
    data = json.loads(output)
    files = []
    for file_info in data["data"][0]["files"]:
        filename = file_info["filename"]
        if LIBCST_SOURCE_MARKER in filename:
            files.append(filename)
    return sorted(files)


def parse_llvm_count(raw: str) -> float:
    value = raw.strip()
    if not value:
        return 0.0
    if value.endswith("k"):
        return float(value[:-1]) * 1_000
    if value.endswith("M"):
        return float(value[:-1]) * 1_000_000
    if value.endswith("G"):
        return float(value[:-1]) * 1_000_000_000
    try:
        return float(value)
    except ValueError:
        return 0.0


def llvm_show_file(variant: str, source_file: str) -> dict[int, tuple[float, str, str]]:
    output = subprocess.check_output(
        [
            "llvm-cov-17",
            "show",
            str(LIBCST_OBJECT),
            f"-instr-profile={latest_profdata(variant)}",
            source_file,
        ],
        text=True,
    )
    lines: dict[int, tuple[float, str, str]] = {}
    for raw_line in output.splitlines():
        match = SHOW_RE.match(raw_line)
        if not match:
            continue
        line_no = int(match.group("line"))
        raw_count = match.group("count")
        source = match.group("source")
        lines[line_no] = (parse_llvm_count(raw_count), raw_count.strip(), source)
    return lines


def load_libcst_line_maps() -> dict[str, dict[str, dict[int, tuple[float, str, str]]]]:
    source_files = llvm_export_files(latest_profdata("append"))
    return {
        variant: {
            source_file: llvm_show_file(variant, source_file)
            for source_file in source_files
        }
        for variant in VARIANTS
    }


def native_line_pct(variant: str) -> float:
    report = sorted((LIBCST_NATIVE_ROOT / variant / "snapshots").glob("snapshot_*.txt"))[-1]
    for line in report.read_text(errors="replace").splitlines():
        if line.startswith("TOTAL"):
            return float(line.split()[9].rstrip("%"))
    raise ValueError(f"No TOTAL line in {report}")


def short_libcst_path(source_file: str) -> str:
    return source_file.split(LIBCST_SOURCE_MARKER, 1)[-1]


def strategy_order_libcst() -> list[str]:
    return sorted(VARIANTS, key=native_line_pct, reverse=True)


def render_libcst_comparison(
    maps: dict[str, dict[str, dict[int, tuple[float, str, str]]]],
    better: str,
    worse: str,
) -> str:
    lines = [
        f"# libcst native: {LABELS[better]} only vs {LABELS[worse]}",
        "",
        f"`{LABELS[better]}` final native line coverage: {native_line_pct(better):.2f}%",
        f"`{LABELS[worse]}` final native line coverage: {native_line_pct(worse):.2f}%",
        "",
        "Lines marked `+` had a positive LLVM line count for the better strategy and zero/no count for the worse strategy.",
        "Context lines are included with `|`; adjacent worse-only lines are marked `-`.",
        "",
    ]
    total_extra = 0
    sections: list[str] = []
    for source_file in sorted(maps[better]):
        better_map = maps[better][source_file]
        worse_map = maps[worse].get(source_file, {})
        all_lines = set(better_map) | set(worse_map)
        better_hit = {line for line in all_lines if better_map.get(line, (0, "", ""))[0] > 0}
        worse_hit = {line for line in all_lines if worse_map.get(line, (0, "", ""))[0] > 0}
        better_only = better_hit - worse_hit
        if not better_only:
            continue
        total_extra += len(better_only)
        section = [
            f"## {short_libcst_path(source_file)}",
            "",
            f"Better-only lines: {len(better_only)}",
            f"Ranges: `{line_ranges(better_only)}`",
            "",
            "```text",
        ]
        for start, end in clusters(better_only):
            section.append(f"@@ {start}-{end} @@")
            for line_no in range(start, end + 1):
                b_count, b_raw, b_source = better_map.get(line_no, (0.0, "", ""))
                w_count, w_raw, w_source = worse_map.get(line_no, (0.0, "", ""))
                source = b_source if b_source else w_source
                if line_no in better_only:
                    marker = "+"
                elif line_no in worse_hit - better_hit:
                    marker = "-"
                else:
                    marker = "|"
                section.append(
                    f"{marker} {line_no:5d}  better:{(b_raw or '0'):<7} worse:{(w_raw or '0'):<7} {source}"
                )
            section.append("")
        section.append("```")
        section.append("")
        sections.append("\n".join(section))
    lines.append(f"Total better-only executed lines: **{total_extra}**")
    lines.append("")
    lines.extend(sections)
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = [
        "# Source-Level Final Coverage Diffs",
        "",
        "These reports show actual source lines executed by the higher-coverage strategy and not by the lower-coverage strategy.",
        "",
    ]

    for target, root in PYTHON_TARGETS.items():
        coverages = load_python_target(target, root)
        order = strategy_order_python(coverages)
        target_dir = OUT_DIR / target
        target_dir.mkdir(parents=True, exist_ok=True)
        index.append(f"## {target}")
        for better, worse in pairwise_better_worse(
            order, lambda variant, cov=coverages: cov[variant].total_pct
        ):
            report = render_python_comparison(target, coverages, better, worse)
            path = target_dir / f"{better}_vs_{worse}_source_diff.md"
            path.write_text(report + "\n")
            index.append(
                f"- [{LABELS[better]} only vs {LABELS[worse]}]"
                f"({target}/{path.name})"
            )
        index.append("")

    libcst_maps = load_libcst_line_maps()
    libcst_order = strategy_order_libcst()
    libcst_dir = OUT_DIR / "libcst"
    libcst_dir.mkdir(parents=True, exist_ok=True)
    index.append("## libcst native")
    for better, worse in pairwise_better_worse(libcst_order, native_line_pct):
        report = render_libcst_comparison(libcst_maps, better, worse)
        path = libcst_dir / f"{better}_vs_{worse}_source_diff.md"
        path.write_text(report + "\n")
        index.append(
            f"- [{LABELS[better]} only vs {LABELS[worse]}]"
            f"(libcst/{path.name})"
        )
    index.append("")

    (OUT_DIR / "index.md").write_text("\n".join(index))
    print(f"Wrote {OUT_DIR / 'index.md'}")


if __name__ == "__main__":
    main()
