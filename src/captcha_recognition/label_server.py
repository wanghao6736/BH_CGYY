"""Flask labeling tool for captcha OCR ground truth.

Workflow: detect bboxes → OCR each box → user corrects text → save.

Usage:
    python -m src.captcha_recognition.label_server
    Then open http://localhost:5050
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from .detector import BoxDetector
from .ocr import OcrRecognizer
from .preprocess import crop_box, image_to_bytes, load_pil_image

app = Flask(__name__, template_folder="label_templates")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

_captcha_dir: Path | None = None
_label_dir: Path | None = None
_detector: BoxDetector | None = None
_ocr: OcrRecognizer | None = None


def get_detector() -> BoxDetector:
    global _detector
    if _detector is None:
        _detector = BoxDetector()
    return _detector


def get_ocr() -> OcrRecognizer:
    global _ocr
    if _ocr is None:
        _ocr = OcrRecognizer()
    return _ocr


def load_labels(image_name: str) -> dict | None:
    label_file = _label_dir / f"{Path(image_name).stem}.json"
    if label_file.exists():
        return json.loads(label_file.read_text())
    return None


def save_labels(image_name: str, data: dict) -> None:
    _label_dir.mkdir(parents=True, exist_ok=True)
    label_file = _label_dir / f"{Path(image_name).stem}.json"
    label_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def detect_and_ocr(image_path: Path) -> list[dict]:
    """Detect boxes and OCR each one. Returns per-box data."""
    detector = get_detector()
    ocr = get_ocr()
    boxes = detector.detect(image_path.read_bytes())
    pil = load_pil_image(image_path)

    results = []
    for idx, box in enumerate(boxes):
        roi = crop_box(pil, box, pad_ratio=0.15)
        ocr_result = ocr.recognize(image_path, box, pad_ratio=0.15)

        # Encode cropped region as base64 PNG for display
        buf = io.BytesIO()
        roi.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        results.append({
            "box_index": idx,
            "box": box.as_list(),
            "ocr_text": ocr_result.text,
            "ocr_confidence": round(ocr_result.confidence, 4),
            "crop_b64": f"data:image/png;base64,{b64}",
        })
    return results


# ── Routes ──────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("label.html")


@app.route("/api/images")
def api_images():
    images = sorted(_captcha_dir.glob("captcha_*.png"))
    items = []
    for img in images:
        name = img.name
        label = load_labels(name)
        status = "labeled" if label and label.get("ground_truth") else "pending"
        items.append({"name": name, "status": status})
    return jsonify({"images": items, "total": len(items)})


@app.route("/api/image/<name>")
def api_image(name: str):
    img_path = _captcha_dir / name
    if not img_path.exists():
        return jsonify({"error": "not found"}), 404

    label = load_labels(name)
    boxes_data = detect_and_ocr(img_path)

    return jsonify({
        "name": name,
        "boxes": boxes_data,
        "label": label,
    })


@app.route("/api/image/<name>/view")
def api_image_view(name: str):
    img_path = _captcha_dir / name
    if not img_path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(str(img_path), mimetype="image/png")


@app.route("/api/image/<name>/save", methods=["POST"])
def api_image_save(name: str):
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    img_path = _captcha_dir / name
    if img_path.exists():
        boxes_data = detect_and_ocr(img_path)
        data["boxes"] = [b["box"] for b in boxes_data]

    data["timestamp"] = int(time.time())
    data["image"] = name
    save_labels(name, data)
    return jsonify({"ok": True})


@app.route("/api/export")
def api_export():
    labels = []
    for lf in sorted(_label_dir.glob("captcha_*.json")):
        data = json.loads(lf.read_text())
        gt = data.get("ground_truth", [])
        labels.append({
            "image": data.get("image", lf.stem + ".png"),
            "text": "".join(gt),
            "chars": ",".join(gt),
            "labeler": data.get("labeler", ""),
        })

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["image", "text", "chars", "labeler"])
    writer.writeheader()
    for row in labels:
        writer.writerow(row)

    output = io.BytesIO(buf.getvalue().encode("utf-8"))
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="captcha_labels.csv",
    )


def main():
    global _captcha_dir, _label_dir

    parser = argparse.ArgumentParser(description="Captcha OCR labeling server")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--captcha-dir", default="CAPTCHA")
    args = parser.parse_args()

    _captcha_dir = Path(args.captcha_dir).resolve()
    _label_dir = _captcha_dir / "labels"

    if not _captcha_dir.exists():
        print(f"Error: captcha directory not found: {_captcha_dir}")
        return

    print(f"Captcha dir: {_captcha_dir}")
    print(f"Label dir:   {_label_dir}")
    print(f"Starting server at http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
