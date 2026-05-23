# ==================================================
# IMPORTS
# ==================================================

import base64
import logging
import tempfile

from pathlib import Path

from modules.config import (
    FRAMES_BEFORE_CURRENT,
    FRAMES_AFTER_CURRENT,
    EXTRACTED_FRAMES_CONTAINER
)

from modules.storage.storage_service import (
    StorageService
)


# ==================================================
# DOWNLOAD FRAME LOCALLY
# ==================================================

def download_frame(
    blob_path: str
):

    storage = StorageService()

    temp_dir = tempfile.gettempdir()

    local_path = (
        Path(temp_dir)
        /
        Path(blob_path).name
    )

    storage.download_blob_to_file(
        container_name=
            EXTRACTED_FRAMES_CONTAINER,

        blob_name=
            blob_path,

        local_file_path=
            str(local_path)
    )

    return str(local_path)


# ==================================================
# IMAGE → BASE64
# ==================================================

def encode_image_to_base64(
    image_path: str
):

    try:

        with open(
            image_path,
            "rb"
        ) as image_file:

            return (
                base64
                .b64encode(
                    image_file.read()
                )
                .decode(
                    "utf-8"
                )
            )

    except Exception:

        logging.exception(
            f"Unable to encode image "
            f"{image_path}"
        )

        return None


# ==================================================
# BUILD IMAGE CONTEXT WINDOW
# ==================================================

def build_image_context(
    frame_manifest: dict,
    current_index: int
):

    sequence = []

    start_index = max(
        0,
        current_index
        -
        FRAMES_BEFORE_CURRENT
    )

    end_index = min(
        len(
            frame_manifest["frames"]
        ),
        current_index
        +
        FRAMES_AFTER_CURRENT
        +
        1
    )

    for index in range(
        start_index,
        end_index
    ):

        frame = (
            frame_manifest[
                "frames"
            ][index]
        )

        local_image = (
            download_frame(
                frame[
                    "blob_path"
                ]
            )
        )

        encoded_image = (
            encode_image_to_base64(
                local_image
            )
        )

        sequence.append(
            {
                "index":
                    index,

                "timestamp_seconds":
                    frame[
                        "timestamp_seconds"
                    ],

                "is_current":
                    (
                        index
                        ==
                        current_index
                    ),

                "base64_image":
                    encoded_image
            }
        )

    return sequence


# ==================================================
# BUILD HUMAN LABEL
# ==================================================

def build_frame_label(
    current_index: int,
    image_index: int
):

    offset = (
        image_index
        -
        current_index
    )

    if offset == 0:

        return (
            "CURRENT FRAME"
        )

    if offset < 0:

        return (
            f"FRAME {offset}"
        )

    return (
        f"FRAME +{offset}"
    )