# --------------------------------------------------
# IMPORTS
# --------------------------------------------------

import logging
import math
import tempfile

from datetime import (
    datetime,
    timezone
)

from pathlib import Path

import cv2

from modules.config import (
    EXTRACTED_FRAMES_CONTAINER,
    FRAME_INTERVAL_SECONDS,
    SEGMENT_ANALYSIS_QUEUE
)

from modules.storage.storage_service import (
    StorageService
)

from modules.storage.queue_service import (
    QueueService
)

# --------------------------------------------------
# FRAME EXTRACTION WORKER
# --------------------------------------------------

def extract_frames(
    video_id: str
):

    logging.info(
        f"Starting frame extraction "
        f"for {video_id}"
    )

    storage = StorageService()

    queue_service = QueueService()

    try:

        # --------------------------------------------------
        # LOAD MANIFEST
        # --------------------------------------------------

        manifest = (
            storage.load_manifest(
                video_id
            )
        )

        # --------------------------------------------------
        # IDEMPOTENCY CHECK
        # --------------------------------------------------

        if manifest.get(
            "frame_extraction_complete",
            False
        ):

            logging.info(
                "Frame extraction already "
                "completed."
            )

            return

        if manifest.get(
            "frame_extraction_started",
            False
        ):

            logging.info(
                "Frame extraction already "
                "running."
            )

            return

        # --------------------------------------------------
        # MARK EXTRACTION STARTED
        # --------------------------------------------------

        storage.update_manifest(
            video_id,
            {
                "status":
                    "frame_extraction",

                "frame_extraction_started":
                    True,

                "frame_extraction_complete":
                    False,

                "last_updated_utc":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            }
        )

        # --------------------------------------------------
        # RELOAD MANIFEST
        # --------------------------------------------------

        manifest = (
            storage.load_manifest(
                video_id
            )
        )

        # --------------------------------------------------
        # TEMP WORKSPACE
        # --------------------------------------------------

        with tempfile.TemporaryDirectory() as temp_dir:

            temp_dir = Path(
                temp_dir
            )

            # --------------------------------------------------
            # DOWNLOAD SOURCE VIDEO
            # --------------------------------------------------

            video_file = (
                temp_dir /
                manifest[
                    "source_blob"
                ]
            )

            storage.download_blob_to_file(
                container_name=
                    manifest[
                        "source_container"
                    ],

                blob_name=
                    manifest[
                        "source_blob"
                    ],

                local_file_path=
                    str(video_file)
            )

            logging.info(
                f"Downloaded video: "
                f"{video_file}"
            )

            # --------------------------------------------------
            # OPEN VIDEO
            # --------------------------------------------------

            cap = cv2.VideoCapture(
                str(video_file)
            )

            if not cap.isOpened():

                raise RuntimeError(
                    "Unable to open video."
                )

            fps = cap.get(
                cv2.CAP_PROP_FPS
            )

            if fps <= 0:

                raise RuntimeError(
                    f"Invalid FPS: {fps}"
                )

            duration_seconds = (
                manifest[
                    "duration_seconds"
                ]
            )

            expected_frames = (
                math.floor(
                    duration_seconds
                    /
                    FRAME_INTERVAL_SECONDS
                )
                + 1
            )

            logging.info(
                f"Expected frame count: "
                f"{expected_frames}"
            )

            # --------------------------------------------------
            # FRAME MANIFEST
            # --------------------------------------------------

            frame_manifest = {

                "video_id":
                    video_id,

                "video_name":
                    manifest[
                        "video_name"
                    ],

                "frame_interval_seconds":
                    FRAME_INTERVAL_SECONDS,

                "total_frames":
                    0,

                "frames":
                    []
            }

            frame_count = 0

            current_time = 0

            missing_frames = []

            # --------------------------------------------------
            # EXTRACT FRAMES
            # --------------------------------------------------

            while current_time <= duration_seconds:

                try:

                    frame_number = int(
                        current_time * fps
                    )

                    cap.set(
                        cv2.CAP_PROP_POS_FRAMES,
                        frame_number
                    )

                    success, frame = (
                        cap.read()
                    )

                    if not success:

                        logging.warning(
                            f"Frame missing at "
                            f"{current_time}s"
                        )

                        missing_frames.append(
                            current_time
                        )

                        current_time += (
                            FRAME_INTERVAL_SECONDS
                        )

                        continue

                    filename = (
                        f"frame_"
                        f"{int(current_time):06d}"
                        f".jpg"
                    )

                    local_frame = (
                        temp_dir /
                        filename
                    )

                    cv2.imwrite(
                        str(local_frame),
                        frame
                    )

                    blob_path = (
                        f"{video_id}/"
                        f"frames/"
                        f"{filename}"
                    )

                    storage.upload_file(
                        container_name=
                            EXTRACTED_FRAMES_CONTAINER,

                        blob_name=
                            blob_path,

                        local_file_path=
                            str(local_frame)
                    )

                    frame_manifest[
                        "frames"
                    ].append(
                        {
                            "frame_index":
                                frame_count,

                            "timestamp_seconds":
                                current_time,

                            "blob_path":
                                blob_path
                        }
                    )

                    frame_count += 1

                except Exception:

                    logging.exception(
                        f"Frame extraction "
                        f"failed at "
                        f"{current_time}s"
                    )

                    missing_frames.append(
                        current_time
                    )

                current_time += (
                    FRAME_INTERVAL_SECONDS
                )

            cap.release()

            # --------------------------------------------------
            # FINALIZE FRAME MANIFEST
            # --------------------------------------------------

            frame_manifest[
                "total_frames"
            ] = frame_count

            storage.save_frame_manifest(
                video_id=
                    video_id,

                frame_manifest=
                    frame_manifest,

                container_name=
                    EXTRACTED_FRAMES_CONTAINER
            )

            # --------------------------------------------------
            # VALIDATION
            # --------------------------------------------------

            logging.info(
                f"Extracted frames: "
                f"{frame_count}"
            )

            logging.info(
                f"Missing frames: "
                f"{len(missing_frames)}"
            )

            # --------------------------------------------------
            # UPDATE MANIFEST
            # --------------------------------------------------

            storage.update_manifest(
                video_id,
                {
                    "status":
                        "frame_extracted",

                    "frame_manifest_created":
                        True,

                    "frame_manifest_blob":
                        (
                            f"extracted-frames/"
                            f"{video_id}/"
                            f"frame_manifest.json"
                        ),

                    "frame_extraction_started":
                        False,

                    "frame_extraction_complete":
                        True,

                    "extracted_frame_count":
                        frame_count,

                    "last_updated_utc":
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                }
            )

            # --------------------------------------------------
            # QUEUE SEGMENT ANALYSIS
            # --------------------------------------------------

            queue_service.send_message(
                SEGMENT_ANALYSIS_QUEUE,
                {
                    "video_id":
                        video_id
                }
            )

            logging.info(
                "Segment analysis "
                "queued successfully"
            )

    except Exception as ex:

        logging.exception(
            f"Frame extraction failed "
            f"for {video_id}"
        )

        storage.update_manifest(
            video_id,
            {
                "processing_error":
                    str(ex),

                "status":
                    "frame_extraction_failed",

                "frame_extraction_started":
                    False
            }
        )

        raise