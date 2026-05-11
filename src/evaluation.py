"""
Shared on-the-fly evaluation harness for Hypothesmith strategies.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Callable

from hypothesis import HealthCheck, given, settings

# Prefer the patched submodule when running scripts from this repository.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_HYPOTHESMITH_SRC = PROJECT_ROOT / "vendor" / "hypothesmith" / "src"

import sys

if VENDOR_HYPOTHESMITH_SRC.exists():
    sys.path.insert(0, str(VENDOR_HYPOTHESMITH_SRC))

from oracles import (  # noqa: E402
    oracle_ast_roundtrip,
    oracle_black_idempotent,
    oracle_tokenize_roundtrip,
)


Oracle = tuple[str, Callable[[str], bool]]
ORACLES: tuple[Oracle, ...] = (
    ("ast", oracle_ast_roundtrip),
    ("tokenize", oracle_tokenize_roundtrip),
    ("black", oracle_black_idempotent),
)
ORACLE_BY_NAME = dict(ORACLES)
ORACLE_NAMES = tuple(ORACLE_BY_NAME)


@dataclass
class EvaluationStats:
    total_programs: int = 0
    successes: int = 0
    failures: int = 0
    elapsed_seconds: float = 0.0

    def record_failure(self) -> None:
        self.failures += 1


def _append_result(results_file: Path, message: str) -> None:
    with results_file.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def _save_failure(
    *,
    failures_dir: Path,
    oracle_name: str,
    index: int,
    source: str,
    error: Exception,
) -> Path:
    out_path = failures_dir / f"{index:04d}_{oracle_name}_failure.py"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# ==================================\n")
        f.write(f"# Oracle: {oracle_name}\n")
        f.write(f"# Example: {index}\n")
        f.write("# ==================================\n\n")
        f.write("## ERROR\n\n")
        f.write(repr(error))
        f.write("\n\n")
        f.write("## TRACEBACK\n\n")
        f.write(traceback.format_exc())
        f.write("\n\n")
        f.write("## SOURCE CODE\n\n")
        f.write(source)
    return out_path


def _save_generated_source(
    *,
    generated_dir: Path,
    index: int,
    status: str,
    source: str,
) -> Path:
    out_path = generated_dir / f"{index:04d}_{status}.py"
    out_path.write_text(source, encoding="utf-8")
    return out_path


def _append_generated_result(
    *,
    manifest_file: Path,
    index: int,
    oracle_name: str,
    status: str,
    source_path: Path,
    failure_path: Path | None = None,
) -> None:
    failure_value = "" if failure_path is None else str(failure_path)
    with manifest_file.open("a", encoding="utf-8") as f:
        f.write(
            f"{index}\t{oracle_name}\t{status}\t{source_path}\t{failure_value}\n"
        )


def _summary(
    *,
    label: str,
    oracle_name: str,
    stats: EvaluationStats,
    results_file: Path,
    failures_dir: Path,
    manifest_file: Path | None,
    termination: str,
) -> str:
    generated_log = ""
    if manifest_file is not None:
        generated_log = f"\nGenerated log:\n{manifest_file}\n"

    return f"""
===================================
{label.title()} Execution Summary
===================================

Oracle              : {oracle_name}
Termination         : {termination}

Total programs      : {stats.total_programs}
Elapsed seconds     : {stats.elapsed_seconds:.2f}

Successful          : {stats.successes}
Failed              : {stats.failures}

Results file:
{results_file}

Failure directory:
{failures_dir}
{generated_log}

===================================
""".strip()


def _run_oracle_evaluation(
    *,
    label: str,
    oracle_name: str,
    oracle: Callable[[str], bool],
    strategy,
    results_dir: Path,
    max_examples: int,
    log_generated: bool,
) -> EvaluationStats:
    """Run one oracle against examples drawn by a Hypothesis strategy."""

    failures_dir = results_dir / "failures"
    generated_dir = results_dir / "generated"
    summaries_dir = results_dir / "summaries"
    results_file = results_dir / "execution_results.txt"
    manifest_file = results_dir / "generated_results.tsv" if log_generated else None

    results_dir.mkdir(parents=True, exist_ok=True)
    failures_dir.mkdir(parents=True, exist_ok=True)
    if log_generated:
        generated_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    results_file.write_text("", encoding="utf-8")
    if manifest_file is not None:
        manifest_file.write_text(
            "example\toracle\tstatus\tsource_path\tfailure_path\n",
            encoding="utf-8",
        )

    stats = EvaluationStats()

    def evaluate_source(source: str) -> None:
        stats.total_programs += 1

        try:
            oracle(source)
        except Exception as error:
            stats.record_failure()
            failure_path = _save_failure(
                failures_dir=failures_dir,
                oracle_name=oracle_name,
                index=stats.total_programs,
                source=source,
                error=error,
            )
            if log_generated:
                assert manifest_file is not None
                source_path = _save_generated_source(
                    generated_dir=generated_dir,
                    index=stats.total_programs,
                    status="failure",
                    source=source,
                )
                _append_generated_result(
                    manifest_file=manifest_file,
                    index=stats.total_programs,
                    oracle_name=oracle_name,
                    status="failure",
                    source_path=source_path,
                    failure_path=failure_path,
                )
            _append_result(
                results_file,
                f"[{oracle_name.upper()} FAILURE] example_{stats.total_programs:04d}",
            )
            return

        stats.successes += 1
        if log_generated:
            assert manifest_file is not None
            source_path = _save_generated_source(
                generated_dir=generated_dir,
                index=stats.total_programs,
                status="pass",
                source=source,
            )
            _append_generated_result(
                manifest_file=manifest_file,
                index=stats.total_programs,
                oracle_name=oracle_name,
                status="pass",
                source_path=source_path,
            )
        _append_result(results_file, f"[PASS] example_{stats.total_programs:04d}")

    started_at = monotonic()
    @settings(
        max_examples=max_examples,
        deadline=None,
        suppress_health_check=[
            HealthCheck.filter_too_much,
            HealthCheck.too_slow,
        ],
    )
    @given(source=strategy)
    def execute_oracle(source: str) -> None:
        evaluate_source(source)

    execute_oracle()
    termination = f"{max_examples} examples"

    stats.elapsed_seconds = monotonic() - started_at

    summary = _summary(
        label=label,
        oracle_name=oracle_name,
        stats=stats,
        results_file=results_file,
        failures_dir=failures_dir,
        manifest_file=manifest_file,
        termination=termination,
    )
    print(summary)
    _append_result(results_file, summary)
    (summaries_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    return stats


def run_evaluation(
    *,
    label: str,
    strategy,
    results_dir: Path,
    oracle_name: str,
    max_examples: int,
    log_generated: bool = False,
) -> EvaluationStats:
    """Run one selected oracle as a Hypothesis test."""

    try:
        oracle = ORACLE_BY_NAME[oracle_name]
    except KeyError as error:
        valid = ", ".join(ORACLE_NAMES)
        raise ValueError(f"unknown oracle {oracle_name!r}; choose from: {valid}") from error

    return _run_oracle_evaluation(
        label=label,
        oracle_name=oracle_name,
        oracle=oracle,
        strategy=strategy,
        results_dir=results_dir / oracle_name,
        max_examples=max_examples,
        log_generated=log_generated,
    )
