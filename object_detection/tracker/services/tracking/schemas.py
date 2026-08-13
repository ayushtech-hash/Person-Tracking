from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass
class Detection:
    bbox: tuple
    confidence: float
    class_id: int


@dataclass
class TrackedDetection:
    bbox: tuple
    confidence: float
    class_id: int
    track_id: int