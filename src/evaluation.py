"""
Shared on-the-fly evaluation harness for Hypothesmith strategies.
"""

from __future__ import annotations

import traceback
import warnings
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Callable

import coverage
from coverage.exceptions import CoverageException
from hypothesis import HealthCheck, Verbosity, given, settings
from hypothesis.errors import FlakyStrategyDefinition

# Prefer the patched submodule when running scripts from this repository.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_HYPOTHESMITH_SRC = PROJECT_ROOT / "vendor" / "hypothesmith" / "src"

import sys

try:
    import signal
except ImportError:  # pragma: no cover - non-Unix fallback
    signal = None

VENDOR_HYPOTHESMITH_DEPS_SRC = PROJECT_ROOT / "vendor" / "hypothesmith" / "deps" / "src"
for vendored_src in (VENDOR_HYPOTHESMITH_SRC, VENDOR_HYPOTHESMITH_DEPS_SRC):
    if vendored_src.exists():
        sys.path.insert(0, str(vendored_src))

from oracles import (  # noqa: E402
    oracle_ast_roundtrip,
    oracle_black_idempotent,
    oracle_tokenize_roundtrip,
)
from target_configs.coverage import (  # noqa: E402
    get_coverage_config,
    supported_coverage_oracles,
)


Oracle = tuple[str, Callable[[str], bool]]
ORACLES: tuple[Oracle, ...] = (
    ("ast", oracle_ast_roundtrip),
    ("tokenize", oracle_tokenize_roundtrip),
    ("black", oracle_black_idempotent),
)
ORACLE_BY_NAME = dict(ORACLES)
ORACLE_NAMES = tuple(ORACLE_BY_NAME)
# Hypothesis exposes max_examples and per-example deadline, but not a total
# wall-clock timeout setting.  Timeout mode therefore uses a very high internal
# cap and stops from the test body once the elapsed budget is consumed.
TIMEOUT_MODE_MAX_EXAMPLES = 1_000_000_000


class _TimeLimitReached(BaseException):
    """Internal control-flow signal for time-limited Hypothesis runs."""


def _exception_chain_contains(
    error: BaseException, exception_type: type[BaseException]
) -> bool:
    """Return True if an exception or its cause/context chain has a type."""

    seen: set[int] = set()
    stack: list[BaseException] = [error]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, exception_type):
            return True
        if current.__cause__ is not None:
            stack.append(current.__cause__)
        if current.__context__ is not None:
            stack.append(current.__context__)
    return False


@dataclass
class EvaluationStats:
    total_programs: int = 0
    successes: int = 0
    failures: int = 0
    elapsed_seconds: float = 0.0

    def record_failure(self) -> None:
        self.failures += 1


@dataclass
class CoverageReport:
    text_path: Path
    json_path: Path
    total_percent: float | None = None
    error: str | None = None


@dataclass
class CoverageSnapshot:
    index: int
    elapsed_seconds: float
    total_programs: int
    report: CoverageReport


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
    coverage_report: CoverageReport | None,
    termination: str,
) -> str:
    generated_log = ""
    if manifest_file is not None:
        generated_log = f"\nGenerated log:\n{manifest_file}\n"

    coverage_log = ""
    if coverage_report is not None:
        coverage_log = (
            f"\nCoverage report:\n{coverage_report.text_path}\n"
            f"Coverage JSON:\n{coverage_report.json_path}\n"
        )
        if coverage_report.total_percent is not None:
            coverage_log += f"Coverage total      : {coverage_report.total_percent:.2f}%\n"
        if coverage_report.error is not None:
            coverage_log += f"Coverage note       : {coverage_report.error}\n"

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
{coverage_log}

===================================
""".strip()


def _write_coverage_reports(
    *,
    cov: coverage.Coverage,
    results_dir: Path,
) -> CoverageReport:
    text_path = results_dir / "coverage.txt"
    json_path = results_dir / "coverage.json"

    try:
        report_buffer = StringIO()
        total_percent = cov.report(file=report_buffer)
        text_path.write_text(report_buffer.getvalue(), encoding="utf-8")
        cov.json_report(outfile=str(json_path))
        return CoverageReport(
            text_path=text_path,
            json_path=json_path,
            total_percent=total_percent,
        )
    except CoverageException as error:
        message = str(error)
        text_path.write_text(message + "\n", encoding="utf-8")
        json_path.write_text("{}\n", encoding="utf-8")
        return CoverageReport(
            text_path=text_path,
            json_path=json_path,
            error=message,
        )


def _write_coverage_note(
    *,
    results_dir: Path,
    message: str,
) -> CoverageReport:
    text_path = results_dir / "coverage.txt"
    json_path = results_dir / "coverage.json"
    text_path.write_text(message + "\n", encoding="utf-8")
    json_path.write_text("{}\n", encoding="utf-8")
    return CoverageReport(
        text_path=text_path,
        json_path=json_path,
        error=message,
    )


def _write_coverage_snapshot(
    *,
    cov: coverage.Coverage,
    snapshots_dir: Path,
    manifest_path: Path,
    snapshot_index: int,
    elapsed_seconds: float,
    total_programs: int,
) -> CoverageSnapshot:
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    stem = f"snapshot_{snapshot_index:04d}_{int(elapsed_seconds):06d}s"
    text_path = snapshots_dir / f"{stem}.txt"
    json_path = snapshots_dir / f"{stem}.json"

    try:
        report_buffer = StringIO()
        total_percent = cov.report(file=report_buffer)
        text_path.write_text(report_buffer.getvalue(), encoding="utf-8")
        cov.json_report(outfile=str(json_path))
        report = CoverageReport(
            text_path=text_path,
            json_path=json_path,
            total_percent=total_percent,
        )
    except CoverageException as error:
        message = str(error)
        text_path.write_text(message + "\n", encoding="utf-8")
        json_path.write_text("{}\n", encoding="utf-8")
        report = CoverageReport(
            text_path=text_path,
            json_path=json_path,
            error=message,
        )

    with manifest_path.open("a", encoding="utf-8") as f:
        total_value = "" if report.total_percent is None else f"{report.total_percent:.2f}"
        error_value = "" if report.error is None else report.error.replace("\n", " ")
        f.write(
            f"{snapshot_index}\t{elapsed_seconds:.2f}\t{total_programs}\t"
            f"{text_path}\t{json_path}\t{total_value}\t{error_value}\n"
        )

    return CoverageSnapshot(
        index=snapshot_index,
        elapsed_seconds=elapsed_seconds,
        total_programs=total_programs,
        report=report,
    )


def _run_oracle_evaluation(
    *,
    label: str,
    oracle_name: str,
    oracle: Callable[[str], bool],
    strategy,
    results_dir: Path,
    max_examples: int | None,
    timeout_seconds: float | None,
    log_generated: bool,
    measure_coverage: bool,
    coverage_snapshot_interval_seconds: float | None,
) -> EvaluationStats:
    """Run one oracle against examples drawn by a Hypothesis strategy."""

    failures_dir = results_dir / "failures"
    generated_dir = results_dir / "generated"
    summaries_dir = results_dir / "summaries"
    results_file = results_dir / "execution_results.txt"
    run_error_file = results_dir / "run_error.log"
    manifest_file = results_dir / "generated_results.tsv" if log_generated else None
    coverage_snapshots_dir = results_dir / "coverage_snapshots"
    coverage_snapshots_manifest = coverage_snapshots_dir / "manifest.tsv"
    coverage_snapshots_errors = coverage_snapshots_dir / "errors.log"

    results_dir.mkdir(parents=True, exist_ok=True)
    failures_dir.mkdir(parents=True, exist_ok=True)
    if log_generated:
        generated_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    results_file.write_text("", encoding="utf-8")
    run_error_file.write_text("", encoding="utf-8")
    if manifest_file is not None:
        manifest_file.write_text(
            "example\toracle\tstatus\tsource_path\tfailure_path\n",
            encoding="utf-8",
        )
    if measure_coverage and coverage_snapshot_interval_seconds is not None:
        coverage_snapshots_dir.mkdir(parents=True, exist_ok=True)
        coverage_snapshots_manifest.write_text(
            "snapshot\telapsed_seconds\ttotal_programs\ttext_path\tjson_path\t"
            "total_percent\terror\n",
            encoding="utf-8",
        )
        coverage_snapshots_errors.write_text("", encoding="utf-8")

    stats = EvaluationStats()
    cov = None
    coverage_report = None
    stats_lock = Lock()
    coverage_lock = Lock()
    coverage_started = False
    snapshot_index = 0
    next_snapshot_elapsed = coverage_snapshot_interval_seconds
    if measure_coverage:
        coverage_config = get_coverage_config(oracle_name)
        assert coverage_config is not None
        if coverage_config.unavailable_reason is None:
            cov = coverage.Coverage(
                branch=True,
                data_file=str(results_dir / ".coverage"),
                source=coverage_config.source,
            )
        else:
            coverage_report = _write_coverage_note(
                results_dir=results_dir,
                message=coverage_config.unavailable_reason,
            )

    started_at = monotonic()

    def time_limit_reached() -> bool:
        if timeout_seconds is None:
            return False
        return monotonic() - started_at >= timeout_seconds

    def start_coverage() -> None:
        nonlocal coverage_started
        if cov is not None and not coverage_started:
            cov.start()
            coverage_started = True

    def stop_coverage() -> None:
        nonlocal coverage_started
        if cov is not None and coverage_started:
            cov.stop()
            coverage_started = False

    def block_timeout_alarm():
        if (
            signal is None
            or not hasattr(signal, "SIGALRM")
            or not hasattr(signal, "pthread_sigmask")
        ):
            return None
        return signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})

    def restore_timeout_alarm(previous_mask) -> None:
        if previous_mask is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)

    def write_coverage_snapshot(snapshot_index: int, elapsed_seconds: float) -> None:
        if cov is None or coverage_snapshot_interval_seconds is None:
            return
        with stats_lock:
            total_programs = stats.total_programs
        with coverage_lock:
            previous_signal_mask = block_timeout_alarm()
            try:
                stop_coverage()
                try:
                    cov.save()
                    _write_coverage_snapshot(
                        cov=cov,
                        snapshots_dir=coverage_snapshots_dir,
                        manifest_path=coverage_snapshots_manifest,
                        snapshot_index=snapshot_index,
                        elapsed_seconds=elapsed_seconds,
                        total_programs=total_programs,
                    )
                finally:
                    start_coverage()
            finally:
                restore_timeout_alarm(previous_signal_mask)

    def write_due_coverage_snapshots() -> None:
        nonlocal snapshot_index, next_snapshot_elapsed
        if (
            cov is None
            or coverage_snapshot_interval_seconds is None
            or next_snapshot_elapsed is None
        ):
            return
        elapsed_seconds = monotonic() - started_at
        while elapsed_seconds >= next_snapshot_elapsed:
            snapshot_index += 1
            try:
                write_coverage_snapshot(
                    snapshot_index=snapshot_index,
                    elapsed_seconds=next_snapshot_elapsed,
                )
            except Exception as error:  # pragma: no cover - diagnostic path
                with coverage_snapshots_errors.open("a", encoding="utf-8") as f:
                    f.write(
                        f"snapshot {snapshot_index} at "
                        f"{next_snapshot_elapsed:.2f}s failed: "
                        f"{type(error).__name__}: {error}\n"
                    )
            next_snapshot_elapsed += coverage_snapshot_interval_seconds

    def evaluate_source(source: str) -> None:
        with stats_lock:
            stats.total_programs += 1
            example_index = stats.total_programs

        try:
            oracle(source)
        except Exception as error:
            with stats_lock:
                stats.record_failure()
                failure_path = _save_failure(
                    failures_dir=failures_dir,
                    oracle_name=oracle_name,
                    index=example_index,
                    source=source,
                    error=error,
                )
                if log_generated:
                    assert manifest_file is not None
                    source_path = _save_generated_source(
                        generated_dir=generated_dir,
                        index=example_index,
                        status="failure",
                        source=source,
                    )
                    _append_generated_result(
                        manifest_file=manifest_file,
                        index=example_index,
                        oracle_name=oracle_name,
                        status="failure",
                        source_path=source_path,
                        failure_path=failure_path,
                    )
                _append_result(
                    results_file,
                    f"[{oracle_name.upper()} FAILURE] example_{example_index:04d}",
                )
            return

        with stats_lock:
            stats.successes += 1
            if log_generated:
                assert manifest_file is not None
                source_path = _save_generated_source(
                    generated_dir=generated_dir,
                    index=example_index,
                    status="pass",
                    source=source,
                )
                _append_generated_result(
                    manifest_file=manifest_file,
                    index=example_index,
                    oracle_name=oracle_name,
                    status="pass",
                    source_path=source_path,
                )
            _append_result(results_file, f"[PASS] example_{example_index:04d}")

    hypothesis_max_examples = (
        max_examples if max_examples is not None else TIMEOUT_MODE_MAX_EXAMPLES
    )
    settings_kwargs = {
        "max_examples": hypothesis_max_examples,
        "deadline": None,
        "suppress_health_check": [
            HealthCheck.filter_too_much,
            HealthCheck.too_slow,
        ],
    }
    if timeout_seconds is not None:
        settings_kwargs["verbosity"] = Verbosity.quiet

    @settings(
        **settings_kwargs,
    )
    @given(source=strategy)
    def execute_oracle(source: str) -> None:
        if time_limit_reached():
            raise _TimeLimitReached
        evaluate_source(source)
        write_due_coverage_snapshots()
        if time_limit_reached():
            raise _TimeLimitReached

    if cov is not None:
        start_coverage()

    previous_sigalrm_handler = None
    timeout_alarm_installed = False

    def raise_time_limit(_signum, _frame) -> None:
        raise _TimeLimitReached

    if timeout_seconds is not None and signal is not None and hasattr(signal, "SIGALRM"):
        try:
            previous_sigalrm_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, raise_time_limit)
            signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
            timeout_alarm_installed = True
        except (AttributeError, ValueError):
            timeout_alarm_installed = False

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            try:
                execute_oracle()
            except _TimeLimitReached:
                pass
            except FlakyStrategyDefinition as error:
                if time_limit_reached() and _exception_chain_contains(
                    error, _TimeLimitReached
                ):
                    pass
                else:
                    run_error_file.write_text(traceback.format_exc(), encoding="utf-8")
                    raise
            except BaseException:
                run_error_file.write_text(traceback.format_exc(), encoding="utf-8")
                raise
    finally:
        if timeout_alarm_installed:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous_sigalrm_handler)
        if cov is not None:
            write_due_coverage_snapshots()
            with coverage_lock:
                previous_signal_mask = block_timeout_alarm()
                try:
                    stop_coverage()
                    cov.save()
                    coverage_report = _write_coverage_reports(
                        cov=cov,
                        results_dir=results_dir,
                    )
                finally:
                    restore_timeout_alarm(previous_signal_mask)
    if timeout_seconds is None:
        assert max_examples is not None
        termination = f"{max_examples} examples"
    else:
        termination = f"{timeout_seconds:g} seconds"

    stats.elapsed_seconds = monotonic() - started_at

    summary = _summary(
        label=label,
        oracle_name=oracle_name,
        stats=stats,
        results_file=results_file,
        failures_dir=failures_dir,
        manifest_file=manifest_file,
        coverage_report=coverage_report,
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
    max_examples: int | None,
    timeout_seconds: float | None = None,
    log_generated: bool = False,
    measure_coverage: bool = False,
    coverage_snapshot_interval_seconds: float | None = None,
) -> EvaluationStats:
    """Run one selected oracle as a Hypothesis test."""

    if (max_examples is None) == (timeout_seconds is None):
        raise ValueError(
            "choose exactly one termination mode: max_examples or timeout_seconds"
        )

    try:
        oracle = ORACLE_BY_NAME[oracle_name]
    except KeyError as error:
        valid = ", ".join(ORACLE_NAMES)
        raise ValueError(f"unknown oracle {oracle_name!r}; choose from: {valid}") from error

    if measure_coverage and get_coverage_config(oracle_name) is None:
        supported = ", ".join(supported_coverage_oracles())
        raise ValueError(
            f"coverage is currently supported only for: {supported}"
        )
    if coverage_snapshot_interval_seconds is not None and not measure_coverage:
        raise ValueError(
            "coverage_snapshot_interval_seconds requires measure_coverage=True"
        )
    if coverage_snapshot_interval_seconds is not None and timeout_seconds is None:
        raise ValueError(
            "coverage snapshots are only supported for timeout-based evaluations"
        )

    return _run_oracle_evaluation(
        label=label,
        oracle_name=oracle_name,
        oracle=oracle,
        strategy=strategy,
        results_dir=results_dir / oracle_name,
        max_examples=max_examples,
        timeout_seconds=timeout_seconds,
        log_generated=log_generated,
        measure_coverage=measure_coverage,
        coverage_snapshot_interval_seconds=coverage_snapshot_interval_seconds,
    )
