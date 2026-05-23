# ==================================================
# IMPORTS
# ==================================================

from modules.config import (
    TRANSCRIPT_CONTEXT_SECONDS,
    SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES
)

from modules.transcript.transcript_utils import (
    get_transcript_for_timestamp
)


# ==================================================
# FIND FRAME INDEX
# ==================================================

def find_frame_index(
    frame_manifest: dict,
    timestamp_seconds: float
):

    for index, frame in enumerate(
        frame_manifest["frames"]
    ):

        if (
            frame["timestamp_seconds"]
            ==
            timestamp_seconds
        ):

            return index

    return -1


# ==================================================
# BUILD TRANSCRIPT CONTEXT
# ==================================================

def build_transcript_context(
    transcript_entries: list,
    timestamp_seconds: float
):

    return (
        get_transcript_for_timestamp(
            transcript_entries=
                transcript_entries,

            target_seconds=
                timestamp_seconds,

            context_window_seconds=
                TRANSCRIPT_CONTEXT_SECONDS
        )
    )


# ==================================================
# BUILD PREVIOUS MEMORY CONTEXT
# ==================================================

def build_previous_context(
    previous_frames_buffer: list
):

    if not previous_frames_buffer:

        return ""

    context_parts = []

    for frame in previous_frames_buffer:

        context_parts.append(
            (
                f"Timestamp: "
                f"{frame['timestamp_seconds']}\n\n"

                f"Transcript:\n"
                f"{frame['speech_context']}\n\n"

                f"Description:\n"
                f"{frame['ai_visual_description']}\n"
            )
        )

    return "\n\n".join(
        context_parts
    )


# ==================================================
# UPDATE MEMORY BUFFER
# ==================================================

def update_previous_buffer(
    buffer: list,
    frame_result: dict
):

    buffer.append(
        frame_result
    )

    while (
        len(buffer)
        >
        SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES
    ):

        buffer.pop(0)

    return buffer