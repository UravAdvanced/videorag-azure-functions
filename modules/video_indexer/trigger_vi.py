from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import logging

from modules.config import (
    INPUT_VIDEOS_CONTAINER,
    FRAME_INTERVAL_SECONDS,
    TRANSCRIPT_CONTEXT_SECONDS,
    SEGMENT_DURATION_SECONDS,
    SUPPORTED_VIDEO_EXTENSIONS
)

from modules.storage.storage_service import (
    StorageService
)

from modules.video_indexer.video_indexer_service import (
    VideoIndexerService
)


def _utc_now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


def _callback_host(
    callback_url: str
) -> str:

    try:

        return urlparse(
            callback_url
        ).netloc

    except Exception:

        return ""


def process_uploaded_video(
    blob_name: str,
    sas_url: str,
    callback_url: str
):

    extension = (
        Path(blob_name)
        .suffix
        .lower()
    )

    if extension not in SUPPORTED_VIDEO_EXTENSIONS:

        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    if not callback_url:

        raise RuntimeError(
            "VIDEO_INDEXER_CALLBACK_URL is empty. "
            "Refusing to submit video without callback URL."
        )

    logging.info(
        f"Processing upload: {blob_name}"
    )

    logging.warning(
        f"Video Indexer callback URL present: {bool(callback_url)}"
    )

    logging.warning(
        f"Video Indexer callback URL host: {_callback_host(callback_url)}"
    )

    storage = StorageService()

    vi_service = VideoIndexerService()

    video_name = (
        Path(blob_name)
        .stem
    )

    submission = vi_service.submit_video(
        video_name=video_name,
        video_url=sas_url,
        callback_url=callback_url
    )

    logging.info(
        f"Video Indexer submit response = {submission}"
    )

    vi_video_id = submission[
        "id"
    ]

    logging.info(
        f"Video Indexer video id = {vi_video_id}"
    )

    now = _utc_now()

    manifest = {
        "video_id":
            vi_video_id,

        "video_indexer_video_id":
            vi_video_id,

        "video_name":
            video_name,

        "source_container":
            INPUT_VIDEOS_CONTAINER,

        "source_blob":
            blob_name,

        "insights_blob":
            "",

        "duration_seconds":
            0,

        "video_duration_source":
            "video_indexer",

        "frame_interval_seconds":
            FRAME_INTERVAL_SECONDS,

        "transcript_context_seconds":
            TRANSCRIPT_CONTEXT_SECONDS,

        "segment_duration_seconds":
            SEGMENT_DURATION_SECONDS,

        "transcript_entries_count":
            0,

        "status":
            "submitted",

        "submitted_utc":
            now,

        "last_updated_utc":
            now,

        "callback_received":
            False,

        "callback_url_present_at_submit":
            bool(
                callback_url
            ),

        "callback_url_host":
            _callback_host(
                callback_url
            ),

        "video_indexer_state":
            "submitted",

        "video_indexed_utc":
            "",

        "insights_downloaded":
            False,

        "insights_downloaded_utc":
            "",

        "process_vi_output_queued":
            False,

        "process_vi_output_queued_utc":
            "",

        "frame_manifest_created":
            False,

        "frame_manifest_blob":
            "",

        "frame_extraction_started":
            False,

        "frame_extraction_complete":
            False,

        "segments_created":
            False,

        "segment_analysis_started":
            False,

        "segment_analysis_complete":
            False,

        "aggregation_complete":
            False,

        "completed_utc":
            "",

        "processing_error":
            "",

        "total_segments":
            0,

        "completed_segments":
            0,

        "extracted_frame_count":
            0
    }

    storage.save_manifest(
        manifest[
            "video_id"
        ],
        manifest
    )

    logging.info(
        f"Manifest saved: {manifest['video_id']}.json"
    )

    return manifest