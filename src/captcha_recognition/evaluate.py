"""Evaluation framework for captcha recognition accuracy.

Computes per-character accuracy, exact match rate, confusion matrix,
and per-source breakdown against ground truth labels.

Usage:
    python src/captcha_recognition/evaluate.py --labels CAPTCHA/labels/ --modes ocr,match,fuse
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .pipeline import CaptchaRecognizer


def load_labels(label_dir: Path) -> dict[str, dict]:
    """Load all label JSON files keyed by image filename."""
    labels: dict[str, dict] = {}
    for lf in sorted(label_dir.glob("captcha_*.json")):
        data = json.loads(lf.read_text())
        name = data.get("image", lf.stem + ".png")
        labels[name] = data
    return labels


def compute_confusion(gt: list[str], pred: list[str]) -> list[tuple[str, str]]:
    """Build (gt_char, pred_char) pairs aligned by position.
    Pads shorter list with empty strings.
    """
    pairs = []
    max_len = max(len(gt), len(pred))
    for i in range(max_len):
        g = gt[i] if i < len(gt) else ""
        p = pred[i] if i < len(pred) else ""
        pairs.append((g, p))
    return pairs


def evaluate_one(
    recognizer: CaptchaRecognizer,
    image_path: Path,
    ground_truth: list[str],
    gt_boxes: list[list[int]] | None,
    mode: str,
    known_chars: list[str],
) -> dict:
    """Evaluate a single image in a given mode.

    Aligns ground truth and predictions by spatial position (left-to-right x1).
    Falls back to index-based comparison if gt_boxes is not available.
    """
    img_bytes = image_path.read_bytes()
    result = recognizer.recognize(img_bytes, known_chars=known_chars, mode=mode)

    # Filter out invalid markers from ground truth
    valid_gt = [g for g in ground_truth if g != "__INVALID__"]

    # Sort predictions left-to-right by box x1
    pred_sorted = sorted(result.selected, key=lambda c: c.box.x1)
    pred_texts = [c.text for c in pred_sorted]

    # Sort ground truth left-to-right if boxes are available
    if gt_boxes and len(gt_boxes) == len(ground_truth):
        gt_with_boxes = [(g, b) for g, b in zip(ground_truth, gt_boxes) if g != "__INVALID__"]
        gt_with_boxes.sort(key=lambda x: x[1][0])
        gt_sorted = [g for g, _ in gt_with_boxes]
    else:
        gt_sorted = list(valid_gt)

    # Align by position (left-to-right)
    pairs = compute_confusion(gt_sorted, pred_texts)
    correct = sum(1 for g, p in pairs if g == p and g)
    total = len(pairs)

    # Per-source breakdown: align by box position in the sorted order
    source_correct: dict[str, int] = defaultdict(int)
    source_total: dict[str, int] = defaultdict(int)
    for c in pred_sorted:
        src = c.source
        pos = c.box_index
        if pos < len(ground_truth) and ground_truth[pos] == c.text:
            source_correct[src] = source_correct.get(src, 0) + 1
        source_total[src] = source_total.get(src, 0) + 1

    exact_match = (len(pred_texts) == len(gt_sorted) and len(gt_sorted) > 0 and
                   all(g == p for g, p in pairs))

    return {
        "image": image_path.name,
        "mode": mode,
        "ground_truth": gt_sorted,
        "gt_raw": [g for g in ground_truth if g != "__INVALID__"],
        "predicted": pred_texts,
        "pred_text": "".join(pred_texts),
        "gt_text": "".join(gt_sorted),
        "correct": correct,
        "total": total,
        "accuracy": correct / max(total, 1),
        "exact_match": exact_match,
        "box_count": len(result.boxes),
        "pred_count": len(pred_texts),
        "sources": [c.source for c in pred_sorted],
        "confidences": [round(c.confidence, 4) for c in pred_sorted],
        "source_correct": dict(source_correct),
        "source_total": dict(source_total),
        "warnings": result.warnings,
        "pairs": [(g, p) for g, p in pairs],
    }


def evaluate_all(
    image_dir: Path,
    labels: dict[str, dict],
    known_chars: list[str],
    modes: list[str],
) -> dict:
    """Evaluate all labeled images across all modes."""
    recognizer = CaptchaRecognizer()
    per_image: list[dict] = []

    for name, label in sorted(labels.items()):
        img_path = image_dir / name
        if not img_path.exists():
            print(f"  [skip] image not found: {name}")
            continue

        gt = label.get("ground_truth", [])
        gt_boxes = label.get("boxes")
        if not gt or not any(gt):
            continue

        for mode in modes:
            r = evaluate_one(recognizer, img_path, gt, gt_boxes, mode, known_chars)
            per_image.append(r)

    # Aggregate metrics
    by_mode: dict[str, dict] = {}
    for mode in modes:
        mode_results = [r for r in per_image if r["mode"] == mode]
        n = len(mode_results)
        if n == 0:
            by_mode[mode] = {"count": 0}
            continue

        total_correct = sum(r["correct"] for r in mode_results)
        total_chars = sum(r["total"] for r in mode_results)
        exact_matches = sum(1 for r in mode_results if r["exact_match"])

        # Aggregate source breakdown
        source_correct: dict[str, int] = defaultdict(int)
        source_total: dict[str, int] = defaultdict(int)
        for r in mode_results:
            for src, cnt in r["source_correct"].items():
                source_correct[src] += cnt
            for src, cnt in r["source_total"].items():
                source_total[src] += cnt

        source_acc = {}
        for src in source_total:
            source_acc[src] = round(source_correct.get(src, 0) / max(source_total[src], 1), 4)

        # Build confusion matrix
        confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in mode_results:
            for g, p in r["pairs"]:
                if g or p:
                    confusion[g][p] += 1

        by_mode[mode] = {
            "count": n,
            "total_chars": total_chars,
            "total_correct": total_correct,
            "char_accuracy": round(total_correct / max(total_chars, 1), 4),
            "exact_matches": exact_matches,
            "exact_match_rate": round(exact_matches / n, 4),
            "source_accuracy": source_acc,
            "confusion": {g: dict(p) for g, p in confusion.items()},
        }

    return {"per_image": per_image, "by_mode": by_mode, "modes": modes}


def save_results(results: dict, output_dir: Path, ts: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Summary JSON
    summary = {
        "timestamp": ts,
        "modes": results["modes"],
        "by_mode": results["by_mode"],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )

    # Per-image CSV
    csv_path = output_dir / "per_image.csv"
    fieldnames = [
        "image", "mode", "gt_text", "pred_text", "correct", "total",
        "accuracy", "exact_match", "box_count", "sources", "confidences",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results["per_image"]:
            r_copy = dict(r)
            r_copy["sources"] = ",".join(r_copy["sources"])
            r_copy["confidences"] = ",".join(str(c) for c in r_copy["confidences"])
            writer.writerow(r_copy)

    # Confusion CSV per mode
    for mode, info in results["by_mode"].items():
        if not info.get("confusion"):
            continue
        cf_path = output_dir / f"confusion_{mode}.csv"
        with open(cf_path, "w", newline="") as f:
            chars = sorted(set(info["confusion"].keys()) |
                          {p for v in info["confusion"].values() for p in v})
            writer = csv.writer(f)
            writer.writerow([""] + chars)
            for g in chars:
                row = [g]
                for p in chars:
                    row.append(info["confusion"].get(g, {}).get(p, 0))
                writer.writerow(row)

    print(f"Results saved to {output_dir}")


def print_summary(results: dict) -> None:
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    for mode, info in results["by_mode"].items():
        if not info.get("count"):
            print(f"\n  {mode}: no results")
            continue
        print(f"\n  [{mode}]  images={info['count']}  "
              f"char_acc={info['char_accuracy']:.2%}  "
              f"exact_match={info['exact_match_rate']:.2%}  "
              f"({info['exact_matches']}/{info['count']})")
        if info.get("source_accuracy"):
            print(f"    Per source:")
            for src, acc in sorted(info["source_accuracy"].items()):
                total = sum(
                    1 for r in results["per_image"]
                    if r["mode"] == mode and src in r.get("source_total", {})
                )
                print(f"      {src:25s}: {acc:.2%}")

    # Top confusions
    for mode, info in results["by_mode"].items():
        if not info.get("confusion"):
            continue
        errors = []
        for g, pdict in info["confusion"].items():
            for p, cnt in pdict.items():
                if g != p and g and p and cnt > 0:
                    errors.append((g, p, cnt))
        errors.sort(key=lambda x: -x[2])
        if errors:
            print(f"\n  [{mode}] Top confusions:")
            for g, p, cnt in errors[:10]:
                print(f"    '{g}' -> '{p}': {cnt} times")


def main():
    parser = argparse.ArgumentParser(description="Evaluate captcha recognition accuracy")
    parser.add_argument(
        "--labels",
        default="CAPTCHA/labels",
        help="Directory containing label JSON files",
    )
    parser.add_argument(
        "--image-dir",
        default="CAPTCHA",
        help="Directory containing captcha images",
    )
    parser.add_argument(
        "--modes",
        default="ocr,match,fuse",
        help="Comma-separated modes to evaluate",
    )
    parser.add_argument(
        "--known",
        default="工,学,院,测",
        help="Comma-separated known characters",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: output/eval/<timestamp>)",
    )
    args = parser.parse_args()

    known_chars = [c.strip() for c in args.known.split(",") if c.strip()]
    modes = [m.strip() for m in args.modes.split(",")]
    label_dir = Path(args.labels)
    image_dir = Path(args.image_dir)

    if not label_dir.exists():
        print(f"Error: labels directory not found: {label_dir}")
        print("Run the labeling tool first to create ground truth labels.")
        sys.exit(1)

    labels = load_labels(label_dir)
    print(f"Loaded {len(labels)} labeled images")

    results = evaluate_all(image_dir, labels, known_chars, modes)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output) if args.output else Path(f"output/eval/{ts}")
    save_results(results, output_dir, ts)
    print_summary(results)


if __name__ == "__main__":
    main()
