from dataclasses import dataclass
from typing import List


@dataclass
class FrameRecord:

    timestamp_seconds: float

    frame_blob_path: str


@dataclass
class FrameManifest:

    video_id: str

    video_name: str

    frame_interval_seconds: int

    total_frames: int

    frames: List[FrameRecord]