"""Validate the SHIPPED verify() path end-to-end.

Drives CaptchaRecognizer.verify (the exact method captcha_service uses) over
the labeled set with production-faithful K-subsets, and reports the two numbers
that matter when refetch is rate-limited:
  accept%    = samples where verdict.complete (we'd submit)
  precision  = of accepted samples, fraction with every click on its gt box
A wrong submit burns a real attempt; an abstain costs one (rate-limited) refetch.
"""

from __future__ import annotations

import json
import random
import sys
from itertools import combinations
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.captcha_recognition import CaptchaRecognizer

CAPTCHA_DIR = PROJECT_ROOT / "CAPTCHA"
LABEL_DIR = CAPTCHA_DIR / "labels"
SEED = 1234
K = 3
SUBSETS_PER_IMAGE = 4


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def main():
    recognizer = CaptchaRecognizer()
    rng = random.Random(SEED)

    images = 0
    accepted = 0
    correct_accepted = 0
    abstain_but_recoverable = 0  # abstained yet all clicks were actually right

    for lf in sorted(LABEL_DIR.glob("captcha_*.json")):
        data = json.loads(lf.read_text())
        name = data.get("image", lf.stem + ".png")
        img_path = CAPTCHA_DIR / name
        if not img_path.exists():
            continue
        pairs = [(c, b) for c, b in zip(data.get("ground_truth", []), data.get("boxes", []))
                 if c != "__INVALID__"]
        seen, uniq = set(), []
        for c, b in pairs:
            if c not in seen:
                seen.add(c)
                uniq.append((c, b))
        if len(uniq) < K:
            continue
        chars = [c for c, _ in uniq]
        box_of = {c: b for c, b in uniq}

        subsets = list(combinations(range(len(chars)), K))
        rng.shuffle(subsets)
        for idx in subsets[:SUBSETS_PER_IMAGE]:
            word_list = [chars[i] for i in idx]
            rng.shuffle(word_list)
            images += 1
            verdict = recognizer.verify(img_path.read_bytes(), word_list)
            all_right = all(
                c.box is not None and iou(c.box.as_list(), box_of[c.word]) >= 0.3
                for c in verdict.clicks
            )
            if verdict.complete:
                accepted += 1
                if all_right:
                    correct_accepted += 1
            elif all_right:
                abstain_but_recoverable += 1

    acc = accepted / max(images, 1)
    prec = correct_accepted / max(accepted, 1)
    print(f"samples={images}")
    print(f"accept(submit)% = {accepted}/{images} ({acc:.2%})")
    print(f"precision       = {correct_accepted}/{accepted} ({prec:.2%})")
    print(f"refetch%        = {(1-acc):.2%}")
    print(f"E[draws to win] = {1/max(acc*prec, 1e-9):.2f}")
    print(f"abstained-but-actually-correct = {abstain_but_recoverable} "
          f"(cost: needless refetch, not a wrong submit)")


if __name__ == "__main__":
    main()
