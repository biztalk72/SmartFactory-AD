#!/usr/bin/env python3
"""Train and evaluate anomaly detection models using Anomalib.

Usage:
    # Train PatchCore on MVTec AD bottle category
    python ml/scripts/train.py --model patchcore --category bottle --data_root ml/data/mvtec_ad

    # Train EfficientAD
    python ml/scripts/train.py --model efficient_ad --category bottle --data_root ml/data/mvtec_ad

    # Evaluate only (requires checkpoint)
    python ml/scripts/train.py --model patchcore --category bottle --data_root ml/data/mvtec_ad --eval_only --ckpt path/to/model.ckpt
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Train anomaly detection models")
    parser.add_argument("--model", default="patchcore", choices=["patchcore", "efficient_ad"],
                        help="Model architecture")
    parser.add_argument("--category", default="bottle", help="Product category from dataset")
    parser.add_argument("--data_root", default="ml/data/mvtec_ad", help="Path to dataset root")
    parser.add_argument("--output", default="ml/checkpoints", help="Output directory for checkpoints")
    parser.add_argument("--image_size", type=int, default=256, help="Input image size")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size")
    parser.add_argument("--max_epochs", type=int, default=1, help="Max training epochs (PatchCore only needs 1)")
    parser.add_argument("--accelerator", default="auto", choices=["auto", "cpu", "gpu"])
    parser.add_argument("--eval_only", action="store_true", help="Run evaluation only")
    parser.add_argument("--ckpt", default=None, help="Checkpoint path for evaluation")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    if not data_root.exists():
        print(f"✗ Data root not found: {data_root}")
        print("  Run: python ml/scripts/download_dataset.py --dataset mvtec_ad --output ml/data")
        sys.exit(1)

    category_dir = data_root / args.category
    if not category_dir.exists():
        available = sorted([d.name for d in data_root.iterdir() if d.is_dir()])
        print(f"✗ Category '{args.category}' not found. Available: {available}")
        sys.exit(1)

    # ── Import Anomalib ──
    try:
        from anomalib.data import MVTec
        from anomalib.engine import Engine
        from anomalib.models import Patchcore, EfficientAd
    except ImportError:
        print("✗ anomalib not installed. Run: pip install -r ml/requirements.txt")
        sys.exit(1)

    print(f"🔧 Model:    {args.model}")
    print(f"   Category: {args.category}")
    print(f"   Data:     {data_root}")
    print(f"   Output:   {args.output}")

    # ── Setup model ──
    if args.model == "patchcore":
        model = Patchcore(
            backbone="wide_resnet50_2",
            layers=["layer2", "layer3"],
        )
    else:
        model = EfficientAd()

    # ── Setup datamodule ──
    datamodule = MVTec(
        root=str(data_root),
        category=args.category,
        image_size=(args.image_size, args.image_size),
        train_batch_size=args.batch_size,
        eval_batch_size=args.batch_size,
    )

    # ── Setup engine ──
    output_dir = Path(args.output) / args.model / args.category
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = Engine(
        max_epochs=args.max_epochs,
        accelerator=args.accelerator,
        default_root_dir=str(output_dir),
    )

    if args.eval_only:
        if not args.ckpt:
            print("✗ --ckpt required for evaluation mode")
            sys.exit(1)
        print(f"\n📊 Evaluating checkpoint: {args.ckpt}")
        engine.test(model=model, datamodule=datamodule, ckpt_path=args.ckpt)
    else:
        print(f"\n🚀 Training {args.model} on {args.category}...")
        engine.fit(model=model, datamodule=datamodule)

        print(f"\n📊 Evaluating...")
        engine.test(model=model, datamodule=datamodule)

    # Find best checkpoint
    ckpt_dir = output_dir
    ckpts = sorted(ckpt_dir.rglob("*.ckpt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ckpts:
        print(f"\n✅ Best checkpoint: {ckpts[0]}")
        print(f"   Use with: AD_CHECKPOINT_PATH={ckpts[0]}")
    else:
        print("\n⚠ No checkpoint files found in output directory.")


if __name__ == "__main__":
    main()
