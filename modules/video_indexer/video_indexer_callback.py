from datetime import datetime, timezone
import logging

from modules.config import (
    PROCESS_VI_OUTPUT_QUEUE
)

from modules.storage.queue_service import (
    QueueService
)

from modules.storage.storage_service import (
    StorageService
)


def _utc_now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


def process_callback(
    video_id: str
):

    logging.info(
        f"process_callback started for {video_id}"
    )

    storage = StorageService()

    queue_service = QueueService()

    if not storage.manifest_exists(
        video_id
    ):

        raise RuntimeError(
            f"Manifest does not exist for callback video_id={video_id}"
        )

    manifest = storage.load_manifest(
        video_id
    )

    already_downloaded = bool(
        manifest.get(
            "insights_downloaded",
            False
        )
    )

    frame_extraction_complete = bool(
        manifest.get(
            "frame_extraction_complete",
            False
        )
    )

    updates = {
        "callback_received":
            True,

        "video_indexer_state":
            "processed",

        "video_indexed_utc":
            _utc_now(),

        "last_updated_utc":
            _utc_now()
    }

    storage.update_manifest(
        video_id,
        updates
    )

    if (
        already_downloaded
        or
        frame_extraction_complete
    ):

        logging.info(
            f"Callback already processed enough for {video_id}. "
            f"already_downloaded={already_downloaded}, "
            f"frame_extraction_complete={frame_extraction_complete}. "
            f"Skipping duplicate queue."
        )

        return

    queue_service.send_message(
        PROCESS_VI_OUTPUT_QUEUE,
        {
            "video_id":
                video_id,

            "video_indexer_video_id":
                video_id
        }
    )

    storage.update_manifest(
        video_id,
        {
            "process_vi_output_queued":
                True,

            "process_vi_output_queued_utc":
                _utc_now()
        }
    )

    logging.info(
        f"process_vi_output queued for {video_id}"
    )