"""
Stream Python files from BigCode's The Stack into the raw donor corpus.

Usage:
    HF_TOKEN=... venv/bin/python src/fetch_the_stack_python.py --target-count 100000
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import get_token
from tqdm import tqdm


DEFAULT_OUTPUT_DIR = Path("directory/base_programs/donor_corpus/raw")
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "the_stack_python_manifest.tsv"
DEFAULT_TARGET_COUNT = 100_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull Python files from bigcode/the-stack into the raw donor corpus."
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=DEFAULT_TARGET_COUNT,
        help=f"total number of raw Python samples to keep locally (default: {DEFAULT_TARGET_COUNT})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory where raw Python files are written",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="TSV file that records metadata for each saved sample",
    )
    return parser.parse_args()


def existing_sample_indices(output_dir: Path) -> list[int]:
    indices: list[int] = []
    for path in output_dir.glob("sample_*.py"):
        stem = path.stem
        try:
            indices.append(int(stem.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return sorted(indices)


def next_sample_index(output_dir: Path) -> int:
    indices = existing_sample_indices(output_dir)
    if not indices:
        return 1
    return indices[-1] + 1


def ensure_manifest_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "sample_id\thexsha\tsize\tlang\text\tmax_stars_repo_name\tmax_stars_repo_path\n",
        encoding="utf-8",
    )


def append_manifest_row(manifest_path: Path, sample_id: int, sample: dict) -> None:
    with manifest_path.open("a", encoding="utf-8") as f:
        fields = [
            str(sample_id),
            str(sample.get("hexsha", "")),
            str(sample.get("size", "")),
            str(sample.get("lang", "")),
            str(sample.get("ext", "")),
            str(sample.get("max_stars_repo_name", "")),
            str(sample.get("max_stars_repo_path", "")),
        ]
        f.write("\t".join(field.replace("\t", " ").replace("\n", " ") for field in fields))
        f.write("\n")


def main() -> None:
    args = parse_args()
    token = get_token()
    if not token:
        raise SystemExit(
            "No Hugging Face token found. Set HF_TOKEN or run `hf auth login` first."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ensure_manifest_header(args.manifest)

    current_count = len(existing_sample_indices(args.output_dir))
    if current_count >= args.target_count:
        print(
            f"Already have {current_count} samples in {args.output_dir}, "
            f"which meets target {args.target_count}."
        )
        return

    sample_id = next_sample_index(args.output_dir)
    remaining = args.target_count - current_count
    progress = tqdm(total=remaining, desc="Pulling The Stack Python samples")

    dataset = load_dataset(
        "bigcode/the-stack",
        data_dir="data/python",
        split="train",
        streaming=True,
        token=token,
    )

    saved = 0
    for sample in dataset:
        content = sample.get("content", "")
        if not content or not content.strip():
            continue

        output_path = args.output_dir / f"sample_{sample_id}.py"
        output_path.write_text(content, encoding="utf-8")
        append_manifest_row(args.manifest, sample_id, sample)

        sample_id += 1
        saved += 1
        progress.update(1)

        if current_count + saved >= args.target_count:
            break

    progress.close()
    print(
        f"Saved {saved} new Python samples from The Stack. "
        f"Corpus now has {current_count + saved} samples."
    )

    # `datasets` streaming can leave background state that occasionally crashes
    # the interpreter during shutdown in this environment. Exiting here avoids
    # that teardown bug after all file writes are complete.
    os._exit(0)


if __name__ == "__main__":
    main()
