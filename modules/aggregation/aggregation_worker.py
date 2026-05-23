# ==================================================
# IMPORTS
# ==================================================

import logging
import os
import re

from datetime import datetime, timezone

from modules.config import (
    RAG_DATABASE_CONTAINER,
    PROCESSING_CHECKPOINTS_CONTAINER,
    STATUS_COMPLETED
)

from modules.storage.storage_service import StorageService
from modules.checkpoints.checkpoint_service import CheckpointService


# ==================================================
# HELPERS
# ==================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(name: str, default: bool) -> bool:

    raw = os.getenv(name)

    if raw is None:
        return default

    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on"
    }


def _sanitize_name(value: str) -> str:

    if not value:
        return "unknown_video"

    cleaned = re.sub(
        r"[^\w\s-]",
        "",
        value,
        flags=re.UNICODE
    )

    cleaned = re.sub(
        r"[-\s]+",
        "_",
        cleaned
    )

    cleaned = cleaned.strip("_")

    if not cleaned:
        return "unknown_video"

    return cleaned


def _deduplicate_and_sort_frames(frame_results: list) -> list:

    deduped = {}

    for result in frame_results:

        if not isinstance(result, dict):
            continue

        frame_index = result.get("frame_index")
        timestamp = result.get("timestamp_seconds")

        if frame_index is not None:
            key = ("frame_index", int(frame_index))
        else:
            key = ("timestamp", float(timestamp or 0))

        existing = deduped.get(key)

        if existing is None:
            deduped[key] = result
            continue

        existing_status = existing.get("status", "")
        new_status = result.get("status", "")

        if existing_status != "succeeded" and new_status == "succeeded":
            deduped[key] = result

    return sorted(
        deduped.values(),
        key=lambda item: (
            item.get("frame_index", 0),
            item.get("timestamp_seconds", 0)
        )
    )


def _build_final_document(
    video_id: str,
    manifest: dict,
    frame_results: list
) -> dict:

    clean_frames = []

    for result in frame_results:

        speech_context = result.get("speech_context", "")
        description = result.get("ai_visual_description", "")
        combined_context = result.get("combined_context")

        if not combined_context:
            combined_context = speech_context + "\n\n" + description

        clean_frames.append(
            {
                "frame_index": result.get("frame_index"),
                "timestamp_seconds": result.get("timestamp_seconds"),
                "frame_path": result.get("frame_path"),
                "speech_context": speech_context,
                "ai_visual_description": description,
                "combined_context": combined_context,
                "status": result.get("status", "unknown"),
                "error": result.get("error", "")
            }
        )

    succeeded_count = len(
        [
            frame
            for frame in clean_frames
            if frame.get("status") == "succeeded"
        ]
    )

    failed_count = len(
        [
            frame
            for frame in clean_frames
            if frame.get("status") == "failed"
        ]
    )

    video_name = manifest.get("video_name", "")

    return {
        "video_id": video_id,
        "video_indexer_video_id": manifest.get(
            "video_indexer_video_id",
            video_id
        ),
        "video_name": video_name,
        "video_name_sanitized": _sanitize_name(video_name),
        "source_container": manifest.get("source_container", ""),
        "source_blob": manifest.get("source_blob", ""),
        "duration_seconds": manifest.get("duration_seconds", 0),
        "transcript_entries_count": manifest.get(
            "transcript_entries_count",
            0
        ),
        "frame_count": len(clean_frames),
        "frame_result_counts": {
            "total": len(clean_frames),
            "succeeded": succeeded_count,
            "failed": failed_count
        },
        "processing_parameters": {
            "frame_interval_seconds": manifest.get(
                "frame_interval_seconds"
            ),
            "transcript_context_seconds": manifest.get(
                "transcript_context_seconds"
            ),
            "segment_duration_seconds": manifest.get(
                "segment_duration_seconds"
            )
        },
        "generated_utc": _utc_now(),
        "analyzed_frames": clean_frames
    }


# ==================================================
# AGGREGATION WORKER
# ==================================================

def aggregate_video(video_id: str):

    logging.info(
        f"AGGREGATION START video_id={video_id}"
    )

    storage = StorageService()
    checkpoint_service = CheckpointService(storage)

    try:

        manifest = storage.load_manifest(video_id)

        video_name = manifest.get("video_name", video_id)
        video_name_sanitized = _sanitize_name(video_name)

        friendly_output_blob = (
            f"{video_name_sanitized}__{video_id}.json"
        )

        id_output_blob = f"{video_id}.json"
        partial_blob = f"{video_id}.partial.json"

        save_id_copy = _env_bool(
            "SAVE_ID_RAG_COPY",
            False
        )

        delete_partial = _env_bool(
            "DELETE_PARTIAL_RAG_AFTER_FINAL",
            True
        )

        cleanup_checkpoints = _env_bool(
            "CLEANUP_CHECKPOINTS_AFTER_SUCCESS",
            False
        )

        cleanup_manifest = _env_bool(
            "CLEANUP_MANIFEST_AFTER_SUCCESS",
            False
        )

        logging.info(
            f"AGGREGATION OUTPUT video_id={video_id} "
            f"friendly_output_blob={friendly_output_blob} "
            f"save_id_copy={save_id_copy}"
        )

        frame_results = checkpoint_service.load_all_frame_results(video_id)

        if not frame_results:
            raise RuntimeError(
                f"No frame checkpoints found for aggregation: {video_id}"
            )

        clean_results = _deduplicate_and_sort_frames(frame_results)

        final_document = _build_final_document(
            video_id=video_id,
            manifest=manifest,
            frame_results=clean_results
        )

        storage.upload_json(
            RAG_DATABASE_CONTAINER,
            friendly_output_blob,
            final_document
        )

        logging.info(
            f"Saved friendly final RAG JSON: "
            f"{RAG_DATABASE_CONTAINER}/{friendly_output_blob}"
        )

        id_copy_saved = False
        id_copy_deleted = False

        if save_id_copy:

            storage.upload_json(
                RAG_DATABASE_CONTAINER,
                id_output_blob,
                final_document
            )

            id_copy_saved = True

        else:

            if storage.blob_exists(
                RAG_DATABASE_CONTAINER,
                id_output_blob
            ):

                storage.delete_blob(
                    RAG_DATABASE_CONTAINER,
                    id_output_blob
                )

                id_copy_deleted = True

        partial_deleted = False

        if delete_partial:

            if storage.blob_exists(
                RAG_DATABASE_CONTAINER,
                partial_blob
            ):

                storage.delete_blob(
                    RAG_DATABASE_CONTAINER,
                    partial_blob
                )

                partial_deleted = True

        checkpoints_deleted = 0

        if cleanup_checkpoints:

            checkpoints_deleted = storage.delete_blobs_with_prefix(
                PROCESSING_CHECKPOINTS_CONTAINER,
                f"{video_id}/"
            )

        storage.update_manifest(
            video_id,
            {
                "aggregation_complete": True,
                "status": STATUS_COMPLETED,
                "completed_utc": _utc_now(),
                "final_rag_blob": (
                    f"{RAG_DATABASE_CONTAINER}/"
                    f"{friendly_output_blob}"
                ),
                "final_rag_friendly_blob": (
                    f"{RAG_DATABASE_CONTAINER}/"
                    f"{friendly_output_blob}"
                ),
                "final_rag_id_copy_blob": (
                    f"{RAG_DATABASE_CONTAINER}/{id_output_blob}"
                    if id_copy_saved
                    else ""
                ),
                "final_rag_id_copy_saved": id_copy_saved,
                "final_rag_id_copy_deleted": id_copy_deleted,
                "final_rag_frame_count": len(
                    final_document.get("analyzed_frames", [])
                ),
                "partial_rag_deleted": partial_deleted,
                "checkpoints_deleted_after_success": checkpoints_deleted,
                "last_updated_utc": _utc_now()
            }
        )

        if cleanup_manifest:

            storage.delete_blob(
                "processing-manifests",
                f"{video_id}.json"
            )

        logging.info(
            f"AGGREGATION COMPLETE video_id={video_id}"
        )

    except Exception as ex:

        logging.exception(
            f"Aggregation failed for {video_id}: {ex}"
        )

        try:

            storage.update_manifest(
                video_id,
                {
                    "processing_error": str(ex),
                    "status": "aggregation_failed",
                    "last_updated_utc": _utc_now()
                }
            )

        except Exception:

            logging.exception(
                f"Unable to update aggregation failure manifest "
                f"for {video_id}"
            )

        raise