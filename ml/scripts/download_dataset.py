#!/usr/bin/env python3
"""Download and prepare MVTec AD dataset for training.

Usage:
    python ml/scripts/download_dataset.py --dataset mvtec_ad --output ml/data
    python ml/scripts/download_dataset.py --dataset mvtec_ad --category bottle --output ml/data
"""

import argparse
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

DATASETS = {
    "mvtec_ad": {
        "url": "https://www.mydrive.ch/shares/38536/3830184030e49fe74747669442f0f282/download/420938113-1629952094/mvtec_anomaly_detection.tar.xz",
        "categories": [
            "bottle", "cable", "capsule", "carpet", "grid",
            "hazelnut", "leather", "metal_nut", "pill", "screw",
            "tile", "toothbrush", "transistor", "wood", "zipper",
        ],
        "description": "MVTec AD: 5,354 images, 15 categories, 73 defect types",
    },
}


def download_file(url: str, dest: Path, desc: str = "") -> None:
    """Download a file with progress indicator."""
    if dest.exists():
        print(f"  ✓ Already exists: {dest}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  ↓ Downloading {desc or dest.name}...")

    def _progress(count, block_size, total_size):
        pct = count * block_size * 100 // total_size if total_size > 0 else 0
        sys.stdout.write(f"\r    {pct}% ({count * block_size // (1024*1024)}MB)")
        sys.stdout.flush()

    urllib.request.urlretrieve(url, str(dest), reporthook=_progress)
    print()


def extract_tar(archive: Path, dest: Path) -> None:
    """Extract tar.xz archive."""
    print(f"  ⤵ Extracting to {dest} ...")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(archive), "r:xz") as tar:
        tar.extractall(path=str(dest))
    print(f"  ✓ Extracted")


def print_dataset_stats(data_dir: Path) -> None:
    """Print dataset statistics."""
    categories = sorted([d.name for d in data_dir.iterdir() if d.is_dir()])
    print(f"\n📊 Dataset Statistics:")
    print(f"   Categories: {len(categories)}")
    total_train = 0
    total_test = 0
    for cat in categories:
        cat_dir = data_dir / cat
        train_dir = cat_dir / "train" / "good"
        test_dir = cat_dir / "test"
        n_train = len(list(train_dir.glob("*.png"))) if train_dir.exists() else 0
        n_test = sum(len(list(d.glob("*.png"))) for d in test_dir.iterdir() if d.is_dir()) if test_dir.exists() else 0
        total_train += n_train
        total_test += n_test
        print(f"   {cat:15s} | train: {n_train:4d} | test: {n_test:4d}")
    print(f"   {'TOTAL':15s} | train: {total_train:4d} | test: {total_test:4d}")


def main():
    parser = argparse.ArgumentParser(description="Download anomaly detection datasets")
    parser.add_argument("--dataset", default="mvtec_ad", choices=list(DATASETS.keys()))
    parser.add_argument("--category", default=None, help="Download specific category only")
    parser.add_argument("--output", default="ml/data", help="Output directory")
    parser.add_argument("--stats-only", action="store_true", help="Only print stats for existing dataset")
    args = parser.parse_args()

    ds = DATASETS[args.dataset]
    output_dir = Path(args.output)

    print(f"🔧 Dataset: {args.dataset}")
    print(f"   {ds['description']}")

    if args.stats_only:
        data_dir = output_dir / args.dataset
        if data_dir.exists():
            print_dataset_stats(data_dir)
        else:
            print(f"   ✗ Dataset not found at {data_dir}")
        return

    # Download
    archive_path = output_dir / f"{args.dataset}.tar.xz"
    download_file(ds["url"], archive_path, desc=args.dataset)

    # Extract
    data_dir = output_dir / args.dataset
    if not data_dir.exists():
        extract_tar(archive_path, output_dir)
        # MVTec AD extracts to "mvtec_anomaly_detection"
        extracted = output_dir / "mvtec_anomaly_detection"
        if extracted.exists() and not data_dir.exists():
            extracted.rename(data_dir)

    print_dataset_stats(data_dir)
    print(f"\n✅ Dataset ready at: {data_dir}")


if __name__ == "__main__":
    main()
