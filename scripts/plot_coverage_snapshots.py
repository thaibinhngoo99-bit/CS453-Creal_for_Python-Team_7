#!/usr/bin/env python3
"""Plot 15-minute coverage snapshots for the 24h target experiments.

The Python targets use coverage.py JSON snapshots. LibCST uses LLVM native
coverage text reports, so its plotted percentage is line coverage.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape


VARIANTS = ("aggressive", "append", "no_injection")
VARIANT_LABELS = {
    "aggressive": "aggressive",
    "append": "append",
    "no_injection": "no injection",
}
COLORS = {
    "aggressive": "#1f77b4",
    "append": "#d62728",
    "no_injection": "#2ca02c",
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
OUTPUT_DIR = Path("results/coverage_snapshot_graphs")

SNAPSHOT_RE = re.compile(r"snapshot_(\d+)_(\d+)s\.(?:json|txt)$")


@dataclass(frozen=True)
class Point:
    target: str
    variant: str
    seconds: int
    coverage_pct: float
    secondary_a_pct: float | None
    secondary_b_pct: float | None
    source: Path

    @property
    def hours(self) -> float:
        return self.seconds / 3600.0


def parse_snapshot_seconds(path: Path) -> int:
    match = SNAPSHOT_RE.match(path.name)
    if not match:
        raise ValueError(f"Unexpected snapshot name: {path}")
    return int(match.group(2))


def read_python_points(target: str, root: Path) -> list[Point]:
    points: list[Point] = []
    for variant in VARIANTS:
        snapshot_dir = root / variant / target / "coverage_snapshots"
        for path in sorted(snapshot_dir.glob("snapshot_*.json")):
            totals = json.loads(path.read_text())["totals"]
            points.append(
                Point(
                    target=target,
                    variant=variant,
                    seconds=parse_snapshot_seconds(path),
                    coverage_pct=float(totals["percent_covered"]),
                    secondary_a_pct=float(totals["percent_statements_covered"]),
                    secondary_b_pct=float(totals["percent_branches_covered"]),
                    source=path,
                )
            )
    return points


def read_libcst_points() -> list[Point]:
    points: list[Point] = []
    for variant in VARIANTS:
        snapshot_dir = LIBCST_NATIVE_ROOT / variant / "snapshots"
        for path in sorted(snapshot_dir.glob("snapshot_*.txt")):
            total_line = None
            for line in path.read_text(errors="replace").splitlines():
                if line.startswith("TOTAL"):
                    total_line = line
            if total_line is None:
                continue
            cols = total_line.split()
            points.append(
                Point(
                    target="libcst",
                    variant=variant,
                    seconds=parse_snapshot_seconds(path),
                    coverage_pct=float(cols[9].rstrip("%")),
                    secondary_a_pct=float(cols[3].rstrip("%")),
                    secondary_b_pct=float(cols[6].rstrip("%")),
                    source=path,
                )
            )
    return points


def collect_points() -> list[Point]:
    points: list[Point] = []
    for target, root in PYTHON_TARGETS.items():
        points.extend(read_python_points(target, root))
    points.extend(read_libcst_points())
    return points


def nice_bounds(values: list[float]) -> tuple[float, float]:
    lo = min(values)
    hi = max(values)
    padding = max((hi - lo) * 0.12, 1.0)
    y_min = max(0.0, math.floor((lo - padding) / 5.0) * 5.0)
    y_max = min(100.0, math.ceil((hi + padding) / 5.0) * 5.0)
    if y_max <= y_min:
        y_max = min(100.0, y_min + 5.0)
    return y_min, y_max


def points_by_variant(points: list[Point], target: str) -> dict[str, list[Point]]:
    grouped = {variant: [] for variant in VARIANTS}
    for point in points:
        if point.target == target:
            grouped[point.variant].append(point)
    for variant_points in grouped.values():
        variant_points.sort(key=lambda p: p.seconds)
    return grouped


def svg_line(points: list[Point], x, y) -> str:
    coords = " ".join(f"{x(p.hours):.2f},{y(p.coverage_pct):.2f}" for p in points)
    return coords


def overlap_notes(grouped: dict[str, list[Point]]) -> list[str]:
    signatures: dict[tuple[tuple[int, float], ...], list[str]] = {}
    for variant, variant_points in grouped.items():
        signature = tuple((p.seconds, round(p.coverage_pct, 9)) for p in variant_points)
        signatures.setdefault(signature, []).append(variant)
    return [
        "overlap: " + " = ".join(VARIANT_LABELS[v] for v in variants)
        for variants in signatures.values()
        if len(variants) > 1
    ]


def render_panel(
    target: str,
    grouped: dict[str, list[Point]],
    x0: float,
    y0: float,
    width: float,
    height: float,
) -> str:
    all_points = [p for variant_points in grouped.values() for p in variant_points]
    if not all_points:
        return f'<text x="{x0}" y="{y0 + 20}">No data for {escape(target)}</text>'

    left = x0 + 58
    right = x0 + width - 28
    top = y0 + 38
    bottom = y0 + height - 52
    plot_w = right - left
    plot_h = bottom - top
    max_hours = max(24.0, max(p.hours for p in all_points))
    y_min, y_max = nice_bounds([p.coverage_pct for p in all_points])

    def sx(hours: float) -> float:
        return left + (hours / max_hours) * plot_w

    def sy(pct: float) -> float:
        return bottom - ((pct - y_min) / (y_max - y_min)) * plot_h

    parts = [
        f'<text class="title" x="{x0 + 8}" y="{y0 + 22}">{escape(target)}</text>',
        f'<rect class="plot-bg" x="{left}" y="{top}" width="{plot_w}" height="{plot_h}"/>',
    ]

    for hour in (0, 6, 12, 18, 24):
        x_pos = sx(hour)
        parts.append(f'<line class="grid" x1="{x_pos}" y1="{top}" x2="{x_pos}" y2="{bottom}"/>')
        parts.append(f'<text class="tick" x="{x_pos}" y="{bottom + 18}" text-anchor="middle">{hour}h</text>')

    ticks = 4
    for i in range(ticks + 1):
        pct = y_min + ((y_max - y_min) / ticks) * i
        y_pos = sy(pct)
        parts.append(f'<line class="grid" x1="{left}" y1="{y_pos}" x2="{right}" y2="{y_pos}"/>')
        parts.append(
            f'<text class="tick" x="{left - 8}" y="{y_pos + 4}" '
            f'text-anchor="end">{pct:.0f}%</text>'
        )

    parts.append(f'<line class="axis" x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{bottom}"/>')

    for variant in VARIANTS:
        variant_points = grouped[variant]
        if not variant_points:
            continue
        color = COLORS[variant]
        coords = svg_line(variant_points, sx, sy)
        final = variant_points[-1]
        parts.append(
            f'<polyline class="series" points="{coords}" stroke="{color}"/>'
        )
        parts.append(
            f'<circle cx="{sx(final.hours):.2f}" cy="{sy(final.coverage_pct):.2f}" '
            f'r="3.4" fill="{color}"/>'
        )
        parts.append(
            f'<text class="final-label" x="{sx(final.hours) - 6:.2f}" '
            f'y="{sy(final.coverage_pct) - 7:.2f}" text-anchor="end" '
            f'fill="{color}">{final.coverage_pct:.2f}%</text>'
        )

    legend_x = x0 + width - 285
    legend_y = y0 + 20
    for idx, variant in enumerate(VARIANTS):
        x_start = legend_x + idx * 92
        color = COLORS[variant]
        parts.append(f'<line x1="{x_start}" y1="{legend_y}" x2="{x_start + 18}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text class="legend" x="{x_start + 23}" y="{legend_y + 4}">{VARIANT_LABELS[variant]}</text>')

    metric = "LLVM line coverage" if target == "libcst" else "coverage.py total"
    parts.append(f'<text class="metric" x="{left}" y="{y0 + height - 14}">{metric}</text>')
    for idx, note in enumerate(overlap_notes(grouped)):
        parts.append(
            f'<text class="overlap-note" x="{right}" y="{y0 + height - 14 - idx * 16}" '
            f'text-anchor="end">{escape(note)}</text>'
        )
    return "\n".join(parts)


def render_svg(points: list[Point], targets: list[str], out_path: Path, columns: int) -> None:
    panel_w = 620
    panel_h = 360
    rows = math.ceil(len(targets) / columns)
    width = panel_w * columns
    height = panel_h * rows + 42
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#222}",
        ".title{font-size:22px;font-weight:700}",
        ".metric{font-size:12px;fill:#555}",
        ".tick{font-size:11px;fill:#555}",
        ".legend{font-size:12px;fill:#333}",
        ".final-label{font-size:11px;font-weight:700}",
        ".overlap-note{font-size:12px;fill:#6b4e00;font-weight:700}",
        ".plot-bg{fill:#fff;stroke:#d4d4d4;stroke-width:1}",
        ".grid{stroke:#e9e9e9;stroke-width:1}",
        ".axis{stroke:#666;stroke-width:1.2}",
        ".series{fill:none;stroke-width:2.6;stroke-linejoin:round;stroke-linecap:round}",
        "</style>",
        '<rect width="100%" height="100%" fill="#fafafa"/>',
        '<text class="title" x="18" y="28">24h coverage snapshots, 15-minute cadence</text>',
    ]
    for idx, target in enumerate(targets):
        row = idx // columns
        col = idx % columns
        x0 = col * panel_w
        y0 = 42 + row * panel_h
        parts.append(render_panel(target, points_by_variant(points, target), x0, y0, panel_w, panel_h))
    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n")


def write_csv(points: list[Point], out_path: Path) -> None:
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "target",
                "variant",
                "seconds",
                "hours",
                "coverage_pct",
                "secondary_a_pct",
                "secondary_b_pct",
                "source",
            ]
        )
        for point in sorted(points, key=lambda p: (p.target, p.variant, p.seconds)):
            writer.writerow(
                [
                    point.target,
                    point.variant,
                    point.seconds,
                    f"{point.hours:.6f}",
                    f"{point.coverage_pct:.6f}",
                    "" if point.secondary_a_pct is None else f"{point.secondary_a_pct:.6f}",
                    "" if point.secondary_b_pct is None else f"{point.secondary_b_pct:.6f}",
                    point.source,
                ]
            )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    points = collect_points()
    targets = ["black", "tokenize", "lib2to3", "libcst"]
    write_csv(points, OUTPUT_DIR / "coverage_snapshot_points.csv")
    render_svg(points, targets, OUTPUT_DIR / "coverage_snapshots_all_targets.svg", columns=2)
    for target in targets:
        render_svg(points, [target], OUTPUT_DIR / f"{target}_coverage_snapshots.svg", columns=1)

    print(f"Wrote {OUTPUT_DIR / 'coverage_snapshot_points.csv'}")
    print(f"Wrote {OUTPUT_DIR / 'coverage_snapshots_all_targets.svg'}")
    for target in targets:
        count = sum(1 for p in points if p.target == target)
        print(f"{target}: {count} points")


if __name__ == "__main__":
    main()
