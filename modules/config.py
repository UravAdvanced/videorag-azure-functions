# --------------------------------------------------
# IMPORTS
# --------------------------------------------------

import os


# ==================================================
# ENV HELPERS
# ==================================================

def _get_int(
    name: str,
    default: int
) -> int:

    try:

        return int(
            os.getenv(
                name,
                str(default)
            )
        )

    except Exception:

        return default


def _get_float(
    name: str,
    default: float
) -> float:

    try:

        return float(
            os.getenv(
                name,
                str(default)
            )
        )

    except Exception:

        return default


def _get_bool(
    name: str,
    default: bool
) -> bool:

    raw = os.getenv(
        name
    )

    if raw is None:

        return default

    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on"
    }


# ==================================================
# STORAGE CONTAINERS
# ==================================================

INPUT_VIDEOS_CONTAINER = (
    "input-videos"
)

VIDEO_INDEXER_OUTPUTS_CONTAINER = (
    "video-indexer-outputs"
)

EXTRACTED_FRAMES_CONTAINER = (
    "extracted-frames"
)

RAG_DATABASE_CONTAINER = (
    "rag-database-json"
)

PROCESSING_MANIFESTS_CONTAINER = (
    "processing-manifests"
)

PROCESSING_CHECKPOINTS_CONTAINER = (
    "processing-checkpoints"
)


# ==================================================
# QUEUES
# ==================================================

PROCESS_VI_OUTPUT_QUEUE = (
    "process-vi-output-queue"
)

FRAME_EXTRACTION_QUEUE = (
    "frame-extraction-queue"
)

SEGMENT_ANALYSIS_QUEUE = (
    "segment-analysis-queue"
)

SEGMENT_PROCESSING_QUEUE = (
    "segment-processing-queue"
)

AGGREGATION_QUEUE = (
    "aggregation-queue"
)


# ==================================================
# VIDEO PROCESSING
# ==================================================

FRAME_INTERVAL_SECONDS = _get_int(
    "FRAME_INTERVAL_SECONDS",
    4
)

TRANSCRIPT_CONTEXT_SECONDS = _get_int(
    "TRANSCRIPT_CONTEXT_SECONDS",
    7
)

FRAMES_BEFORE_CURRENT = _get_int(
    "FRAMES_BEFORE_CURRENT",
    5
)

FRAMES_AFTER_CURRENT = _get_int(
    "FRAMES_AFTER_CURRENT",
    5
)

# Preserve successful manual process.py behavior
SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES = _get_int(
    "SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES",
    1
)

TOTAL_CONTEXT_IMAGES = (
    FRAMES_BEFORE_CURRENT
    +
    FRAMES_AFTER_CURRENT
    +
    1
)

if (
    SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES
    >
    FRAMES_BEFORE_CURRENT
):

    raise ValueError(
        "SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES "
        "cannot exceed FRAMES_BEFORE_CURRENT"
    )

SEGMENT_DURATION_SECONDS = _get_int(
    "SEGMENT_DURATION_SECONDS",
    600
)

CHECKPOINT_INTERVAL_FRAMES = _get_int(
    "CHECKPOINT_INTERVAL_FRAMES",
    10
)

SAVE_MANIFEST_INTERVAL_FRAMES = _get_int(
    "SAVE_MANIFEST_INTERVAL_FRAMES",
    5
)

PARTIAL_RAG_SAVE_INTERVAL_FRAMES = _get_int(
    "PARTIAL_RAG_SAVE_INTERVAL_FRAMES",
    5
)

MAX_FRAME_RETRY_COUNT = _get_int(
    "MAX_FRAME_RETRY_COUNT",
    3
)

MAX_VIDEO_SIZE_GB = _get_int(
    "MAX_VIDEO_SIZE_GB",
    20
)

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi"
}


# ==================================================
# SEGMENT ANALYSIS SAFETY
# ==================================================

SEGMENT_BATCH_SIZE_FRAMES = _get_int(
    "SEGMENT_BATCH_SIZE_FRAMES",
    10
)

FRAME_FAILURE_MODE = os.getenv(
    "FRAME_FAILURE_MODE",
    "continue"
).strip().lower()

# Allowed:
# continue  = save failed frame result and continue
# fail_fast = save failed frame result and raise
if FRAME_FAILURE_MODE not in {
    "continue",
    "fail_fast"
}:

    FRAME_FAILURE_MODE = "continue"

MAX_SEGMENT_WORKER_SECONDS = _get_int(
    "MAX_SEGMENT_WORKER_SECONDS",
    540
)


# ==================================================
# GPT ANALYSIS
# ==================================================

GPT_MAX_IMAGES_PER_REQUEST = _get_int(
    "GPT_MAX_IMAGES_PER_REQUEST",
    11
)

MAX_CONTEXT_IMAGES = (
    TOTAL_CONTEXT_IMAGES
)

GPT_MAX_RESPONSE_TOKENS = _get_int(
    "GPT_MAX_RESPONSE_TOKENS",
    700
)

MAX_OPENAI_RETRIES = _get_int(
    "MAX_OPENAI_RETRIES",
    5
)

OPENAI_RETRY_INITIAL_SECONDS = _get_int(
    "OPENAI_RETRY_INITIAL_SECONDS",
    5
)

OPENAI_RETRY_MULTIPLIER = _get_float(
    "OPENAI_RETRY_MULTIPLIER",
    2.0
)

OPENAI_TIMEOUT_SECONDS = _get_int(
    "OPENAI_TIMEOUT_SECONDS",
    120
)

CONTENT_FILTER_FALLBACK_ENABLED = _get_bool(
    "CONTENT_FILTER_FALLBACK_ENABLED",
    True
)

OPENAI_CONTENT_FILTER_RETRY = _get_bool(
    "OPENAI_CONTENT_FILTER_RETRY",
    True
)

OPENAI_TEMPERATURE = _get_float(
    "OPENAI_TEMPERATURE",
    0.2
)


# ==================================================
# RESPONSE VALIDATION
# ==================================================

MIN_DESCRIPTION_LENGTH = _get_int(
    "MIN_DESCRIPTION_LENGTH",
    50
)


# ==================================================
# MANIFEST STATUS VALUES
# ==================================================

STATUS_SUBMITTED = (
    "submitted"
)

STATUS_PROCESSING = (
    "processing"
)

STATUS_VIDEO_INDEXED = (
    "video_indexed"
)

STATUS_FRAME_EXTRACTION = (
    "frame_extraction"
)

STATUS_FRAME_EXTRACTED = (
    "frame_extracted"
)

STATUS_SEGMENTS_CREATED = (
    "segments_created"
)

STATUS_SEGMENT_ANALYSIS = (
    "segment_analysis"
)

STATUS_AGGREGATION = (
    "aggregation"
)

STATUS_COMPLETED = (
    "completed"
)

STATUS_FAILED = (
    "failed"
)

STATUS_SEGMENT_ANALYSIS_COMPLETE = (
    "segment_analysis_complete"
)

STATUS_SEGMENT_ANALYSIS_FAILED = (
    "segment_analysis_failed"
)

STATUS_SEGMENT_ANALYSIS_INCOMPLETE = (
    "segment_analysis_incomplete"
)


# ==================================================
# STANDARD FILENAMES
# ==================================================

FRAME_MANIFEST_FILENAME = (
    "frame_manifest.json"
)

INSIGHTS_FILENAME = (
    "insights.json"
)


# ==================================================
# AZURE OPENAI / AZURE AI SERVICES
# ==================================================

AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT"
)

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY"
)

AZURE_OPENAI_DEPLOYMENT_NAME = (
    os.getenv(
        "AZURE_OPENAI_DEPLOYMENT_NAME"
    )
    or
    os.getenv(
        "AZURE_OPENAI_DEPLOYMENT"
    )
)

AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION",
    ""
)

AZURE_OPENAI_API_KIND = os.getenv(
    "AZURE_OPENAI_API_KIND",
    "auto"
)


# ==================================================
# VIDEO INDEXER
# ==================================================

VIDEO_INDEXER_LOCATION = os.getenv(
    "VIDEO_INDEXER_LOCATION",
    "eastus"
)

VIDEO_INDEXER_ACCOUNT_ID = os.getenv(
    "VIDEO_INDEXER_ACCOUNT_ID"
)

VIDEO_INDEXER_ACCOUNT_NAME = os.getenv(
    "VIDEO_INDEXER_ACCOUNT_NAME"
)

VIDEO_INDEXER_RESOURCE_GROUP = os.getenv(
    "VIDEO_INDEXER_RESOURCE_GROUP"
)

AZURE_SUBSCRIPTION_ID = os.getenv(
    "AZURE_SUBSCRIPTION_ID"
)

VIDEO_INDEXER_CALLBACK_URL = os.getenv(
    "VIDEO_INDEXER_CALLBACK_URL",
    ""
)


# ==================================================
# SEGMENT ANALYSIS CONTEXT LIMITS
# ==================================================

SEGMENT_CONTEXT_PREVIOUS_SEGMENT = _get_bool(
    "SEGMENT_CONTEXT_PREVIOUS_SEGMENT",
    True
)

MAX_MISSING_FRAMES_PER_SEGMENT = _get_int(
    "MAX_MISSING_FRAMES_PER_SEGMENT",
    5
)

PREVIOUS_CONTEXT_MAX_CHARS = _get_int(
    "PREVIOUS_CONTEXT_MAX_CHARS",
    2000
)

TRANSCRIPT_MAX_CHARS = _get_int(
    "TRANSCRIPT_MAX_CHARS",
    4000
)


# ==================================================
# CLEANUP POLICY
# ==================================================

# Keep False for now. We need checkpoints until aggregation succeeds.
# Later, after final RAG JSON is created, we can safely delete:
# - processing checkpoints
# - processing manifests
CLEANUP_PROCESSING_ARTIFACTS_AFTER_SUCCESS = _get_bool(
    "CLEANUP_PROCESSING_ARTIFACTS_AFTER_SUCCESS",
    False
)