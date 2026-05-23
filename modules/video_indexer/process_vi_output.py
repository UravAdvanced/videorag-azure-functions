# --------------------------------------------------
# IMPORTS
# --------------------------------------------------

from datetime import datetime, timezone
import copy
import logging

from modules.config import (
    VIDEO_INDEXER_OUTPUTS_CONTAINER,
    FRAME_EXTRACTION_QUEUE
)

from modules.storage.storage_service import StorageService
from modules.storage.queue_service import QueueService
from modules.video_indexer.video_indexer_service import VideoIndexerService


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_video_indexer_insights(data):

    username_replacement = "AFO"
    account_replacement = "AFO_ACCOUNT"

    sensitive_key_replacements = {
        "userName": username_replacement,
        "username": username_replacement,
        "createdBy": username_replacement,
        "modifiedBy": username_replacement,
        "owner": username_replacement,
        "ownerName": username_replacement,
        "accountId": account_replacement,
        "accountID": account_replacement,
        "accountName": account_replacement
    }

    if isinstance(data, dict):

        sanitized = {}

        for key, value in data.items():

            if key in sensitive_key_replacements:

                sanitized[key] = sensitive_key_replacements[key]

            else:

                sanitized[key] = _sanitize_video_indexer_insights(value)

        return sanitized

    if isinstance(data, list):

        return [
            _sanitize_video_indexer_insights(item)
            for item in data
        ]

    return data


def _count_transcript_entries(insights: dict) -> int:

    try:

        return len(
            insights
            .get("videos", [{}])[0]
            .get("insights", {})
            .get("transcript", [])
        )

    except Exception as ex:

        logging.warning(
            f"Unable to count transcript entries: {ex}"
        )

        return 0


# --------------------------------------------------
# PROCESS VIDEO INDEXER OUTPUT
# --------------------------------------------------

def process_vi_output(video_id: str):

    logging.info(
        f"process_vi_output started for {video_id}"
    )

    storage = StorageService()
    queue_service = QueueService()
    vi_service = VideoIndexerService()

    manifest = storage.load_manifest(video_id)

    if manifest.get("frame_extraction_complete", False):

        logging.info(
            f"Frame extraction already completed for {video_id}. "
            f"Skipping process_vi_output."
        )

        return

    if manifest.get("frame_extraction_started", False):

        logging.info(
            f"Frame extraction already started for {video_id}. "
            f"Skipping duplicate process_vi_output."
        )

        return

    raw_insights = vi_service.download_insights_json(video_id)

    insights = _sanitize_video_indexer_insights(
        copy.deepcopy(raw_insights)
    )

    insights_blob = f"{video_id}/insights.json"

    storage.upload_json(
        VIDEO_INDEXER_OUTPUTS_CONTAINER,
        insights_blob,
        insights
    )

    transcript_entries_count = _count_transcript_entries(insights)

    duration_seconds = vi_service.get_video_duration(video_id)

    storage.update_manifest(
        video_id,
        {
            "insights_blob": (
                f"{VIDEO_INDEXER_OUTPUTS_CONTAINER}/"
                f"{insights_blob}"
            ),
            "insights_downloaded": True,
            "insights_downloaded_utc": _utc_now(),
            "insights_privacy_sanitized": True,
            "insights_username_replacement": "AFO",
            "insights_account_id_replacement": "AFO_ACCOUNT",
            "duration_seconds": duration_seconds,
            "transcript_entries_count": transcript_entries_count,
            "last_updated_utc": _utc_now()
        }
    )

    queue_service.send_message(
        FRAME_EXTRACTION_QUEUE,
        {
            "video_id": video_id
        }
    )

    logging.info(
        f"Frame extraction queued successfully for {video_id}"
    )