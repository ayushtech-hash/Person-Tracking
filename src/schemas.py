from dataclasses import dataclass


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