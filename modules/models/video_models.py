from dataclasses import dataclass, field
from typing import List


@dataclass
class FrameAnalysis:

    timestamp_seconds: float

    frame_path: str

    speech_context: str

    ai_visual_description: str

    previous_context_used: str = ""

    retry_count: int = 0


@dataclass
class SegmentManifest:

    segment_id: int

    start_seconds: float

    end_seconds: float

    status: str = "pending"

    frames_expected: int = 0

    frames_completed: int = 0

    checkpoint_timestamp: float = 0.0

    previous_segment_context: str = ""

    missing_frames: List[float] = field(
        default_factory=list
    )


@dataclass
class VideoManifest:

    video_id: str

    video_indexer_video_id: str

    video_name: str

    source_container: str

    source_blob: str

    insights_blob: str

    duration_seconds: float

    frame_interval_seconds: int

    transcript_context_seconds: int

    segment_duration_seconds: int

    video_duration_source: str = (
        "video_indexer"
    )

    transcript_entries_count: int = 0

    status: str = "submitted"

    submitted_utc: str = ""

    last_updated_utc: str = ""

    callback_received: bool = False

    video_indexer_state: str = "submitted"

    video_indexed_utc: str = ""

    insights_downloaded: bool = False

    insights_downloaded_utc: str = ""

    frame_extraction_started: bool = False

    frame_extraction_complete: bool = False

    segment_analysis_started: bool = False

    segment_analysis_complete: bool = False

    frame_manifest_created: bool = False

    frame_manifest_blob: str = ""

    aggregation_complete: bool = False

    processing_error: str = ""

    total_segments: int = 0

    completed_segments: int = 0

    extracted_frame_count: int = 0

    segments: List[SegmentManifest] = field(
        default_factory=list
    )