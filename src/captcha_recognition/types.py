from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    def pad(self, ratio: float, img_w: int, img_h: int) -> "Box":
        w, h = self.width(), self.height()
        px = int(round(w * ratio))
        py = int(round(h * ratio))
        nx1 = max(0, self.x1 - px)
        ny1 = max(0, self.y1 - py)
        nx2 = min(img_w, self.x2 + px)
        ny2 = min(img_h, self.y2 + py)
        return Box(nx1, ny1, nx2, ny2)

    def as_list(self) -> list[int]:
        return [self.x1, self.y1, self.x2, self.y2]


@dataclass
class OcrResult:
    text: str
    confidence: float
    quality_score: float
    topk: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class MatchResult:
    scores: dict[str, float]
    best_char: str
    best_score: float


@dataclass
class Candidate:
    box_index: int
    box: Box
    text: str
    confidence: float
    source: str
    ocr: OcrResult | None = None
    match: MatchResult | None = None


@dataclass
class RecognitionResult:
    boxes: list[Box]
    selected: list[Candidate]
    all_candidates: list[Candidate]
    target_count: int
    mode: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class Click:
    word: str
    box: Box | None
    confidence: float
    accepted: bool
    reason: str


@dataclass
class VerifyResult:
    word_list: list[str]
    clicks: list[Click]
    complete: bool
