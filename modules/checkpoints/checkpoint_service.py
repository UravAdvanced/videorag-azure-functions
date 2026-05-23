# ==================================================
# IMPORTS
# ==================================================

import logging

from datetime import (
    datetime,
    timezone
)

from modules.config import (
    PROCESSING_CHECKPOINTS_CONTAINER
)


# ==================================================
# CHECKPOINT SERVICE
# ==================================================

class CheckpointService:

    def __init__(
        self,
        storage_service
    ):

        self.storage = storage_service

    # --------------------------------------------------
    # PATH HELPERS
    # --------------------------------------------------

    def progress_blob_name(
        self,
        video_id: str
    ) -> str:

        return (
            f"{video_id}/"
            f"progress.json"
        )

    def legacy_segment_blob_name(
        self,
        video_id: str,
        segment_id: int = 0
    ) -> str:

        return (
            f"{video_id}/"
            f"segment_{segment_id}.json"
        )

    def frame_result_blob_name(
        self,
        video_id: str,
        frame_index: int
    ) -> str:

        return (
            f"{video_id}/"
            f"frames/"
            f"frame_{frame_index:06d}.json"
        )

    def frame_results_prefix(
        self,
        video_id: str
    ) -> str:

        return (
            f"{video_id}/"
            f"frames/"
        )

    # --------------------------------------------------
    # PROGRESS CHECKPOINT
    # --------------------------------------------------

    def save_progress(
        self,
        video_id: str,
        progress_data: dict
    ):

        progress_data = dict(
            progress_data
        )

        progress_data[
            "saved_utc"
        ] = datetime.now(
            timezone.utc
        ).isoformat()

        logging.info(
            f"Saving progress checkpoint "
            f"for {video_id}: "
            f"last_frame_index="
            f"{progress_data.get('last_frame_index')}"
        )

        # New progress checkpoint
        self.storage.upload_json(
            PROCESSING_CHECKPOINTS_CONTAINER,
            self.progress_blob_name(
                video_id
            ),
            progress_data
        )

        # Legacy checkpoint path retained because you
        # already used segment_0.json during debugging.
        self.storage.upload_json(
            PROCESSING_CHECKPOINTS_CONTAINER,
            self.legacy_segment_blob_name(
                video_id,
                0
            ),
            progress_data
        )

    def load_progress(
        self,
        video_id: str
    ):

        return self.storage.download_json_if_exists(
            PROCESSING_CHECKPOINTS_CONTAINER,
            self.progress_blob_name(
                video_id
            )
        )

    # --------------------------------------------------
    # FRAME RESULT CHECKPOINT
    # --------------------------------------------------

    def save_frame_result(
        self,
        video_id: str,
        frame_index: int,
        frame_result: dict
    ):

        frame_result = dict(
            frame_result
        )

        frame_result[
            "checkpoint_saved_utc"
        ] = datetime.now(
            timezone.utc
        ).isoformat()

        blob_name = self.frame_result_blob_name(
            video_id,
            frame_index
        )

        logging.info(
            f"Saving frame checkpoint: "
            f"{PROCESSING_CHECKPOINTS_CONTAINER}/"
            f"{blob_name}"
        )

        self.storage.upload_json(
            PROCESSING_CHECKPOINTS_CONTAINER,
            blob_name,
            frame_result
        )

    def load_frame_result(
        self,
        video_id: str,
        frame_index: int
    ):

        return self.storage.download_json_if_exists(
            PROCESSING_CHECKPOINTS_CONTAINER,
            self.frame_result_blob_name(
                video_id,
                frame_index
            )
        )

    def frame_result_exists(
        self,
        video_id: str,
        frame_index: int
    ) -> bool:

        return self.storage.blob_exists(
            PROCESSING_CHECKPOINTS_CONTAINER,
            self.frame_result_blob_name(
                video_id,
                frame_index
            )
        )

    def list_frame_result_blobs(
        self,
        video_id: str
    ) -> list:

        prefix = self.frame_results_prefix(
            video_id
        )

        blobs = self.storage.list_blobs(
            PROCESSING_CHECKPOINTS_CONTAINER,
            prefix=prefix
        )

        return sorted(
            [
                blob
                for blob in blobs
                if blob.endswith(
                    ".json"
                )
            ]
        )

    def load_all_frame_results(
        self,
        video_id: str
    ) -> list:

        frame_blobs = (
            self.list_frame_result_blobs(
                video_id
            )
        )

        results = []

        for blob_name in frame_blobs:

            try:

                result = self.storage.download_json(
                    PROCESSING_CHECKPOINTS_CONTAINER,
                    blob_name
                )

                results.append(
                    result
                )

            except Exception:

                logging.exception(
                    f"Failed loading frame "
                    f"checkpoint: {blob_name}"
                )

        results.sort(
            key=lambda item: (
                item.get(
                    "frame_index",
                    0
                ),
                item.get(
                    "timestamp_seconds",
                    0
                )
            )
        )

        return results

    def load_frame_results_map(
        self,
        video_id: str
    ) -> dict:

        results = (
            self.load_all_frame_results(
                video_id
            )
        )

        mapped = {}

        for result in results:

            frame_index = result.get(
                "frame_index"
            )

            if frame_index is None:

                continue

            mapped[int(frame_index)] = result

        return mapped

    def count_frame_results(
        self,
        video_id: str
    ) -> int:

        return len(
            self.list_frame_result_blobs(
                video_id
            )
        )