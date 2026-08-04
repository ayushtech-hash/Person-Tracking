from dataclasses import dataclass
from typing import Tuple


@dataclass
class Detection:
    bbox: tuple
    confidence: float
    class_id: int

@dataclass
class TrackedDetection:
    bbox: Tuple[float, float, float, float]
    confidence: float
    class_id: int
    track_id: int