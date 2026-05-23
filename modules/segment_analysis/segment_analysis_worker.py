# ==================================================
# IMPORTS
# ==================================================

import logging
import time

from datetime import datetime, timezone

from modules.config import (
    EXTRACTED_FRAMES_CONTAINER,
    RAG_DATABASE_CONTAINER,
    VIDEO_INDEXER_OUTPUTS_CONTAINER,
    CHECKPOINT_INTERVAL_FRAMES,
    SAVE_MANIFEST_INTERVAL_FRAMES,
    PARTIAL_RAG_SAVE_INTERVAL_FRAMES,
    AGGREGATION_QUEUE,
    SEGMENT_ANALYSIS_QUEUE,
    STATUS_SEGMENT_ANALYSIS,
    STATUS_SEGMENT_ANALYSIS_COMPLETE,
    STATUS_SEGMENT_ANALYSIS_FAILED,
    FRAME_FAILURE_MODE,
    FRAME_INTERVAL_SECONDS,
    TRANSCRIPT_CONTEXT_SECONDS,
    FRAMES_BEFORE_CURRENT,
    FRAMES_AFTER_CURRENT,
    SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES,
    SEGMENT_BATCH_SIZE_FRAMES,
    MAX_SEGMENT_WORKER_SECONDS
)

from modules.storage.storage_service import StorageService
from modules.storage.queue_service import QueueService
from modules.checkpoints.checkpoint_service import CheckpointService

from modules.segment_analysis.image_helper import build_image_context
from modules.segment_analysis.openai_service import OpenAIService

from modules.segment_analysis.frame_context_builder import (
    build_transcript_context,
    build_previous_context
)


# ==================================================
# HELPERS
# ==================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value)


def _build_previous_buffer_from_results(
    results_by_index: dict,
    current_frame_index: int
) -> list:

    if SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES <= 0:
        return []

    previous_results = []

    candidate_indices = [
        index
        for index in results_by_index.keys()
        if index < current_frame_index
    ]

    candidate_indices.sort()

    for index in candidate_indices:
        result = results_by_index[index]

        previous_results.append(
            {
                "timestamp_seconds": result.get("timestamp_seconds", 0),
                "speech_context": result.get("speech_context", ""),
                "ai_visual_description": result.get(
                    "ai_visual_description",
                    ""
                )
            }
        )

    return previous_results[-SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES:]


def _build_partial_rag_document(
    video_id: str,
    manifest: dict,
    frame_results: list
) -> dict:

    sorted_results = sorted(
        frame_results,
        key=lambda item: (
            item.get("frame_index", 0),
            item.get("timestamp_seconds", 0)
        )
    )

    analyzed_frames = []

    for result in sorted_results:
        analyzed_frames.append(
            {
                "frame_index": result.get("frame_index"),
                "timestamp_seconds": result.get("timestamp_seconds"),
                "frame_path": result.get("frame_path"),
                "speech_context": result.get("speech_context", ""),
                "ai_visual_description": result.get(
                    "ai_visual_description",
                    ""
                ),
                "combined_context": result.get("combined_context", ""),
                "status": result.get("status", "unknown"),
                "error": result.get("error", "")
            }
        )

    return {
        "video_id": video_id,
        "video_name": manifest.get("video_name", ""),
        "source_blob": manifest.get("source_blob", ""),
        "duration_seconds": manifest.get("duration_seconds", 0),
        "generated_utc": _utc_now(),
        "is_partial": True,
        "processing_parameters": {
            "frame_interval_seconds": FRAME_INTERVAL_SECONDS,
            "transcript_context_seconds": TRANSCRIPT_CONTEXT_SECONDS,
            "frames_before_current": FRAMES_BEFORE_CURRENT,
            "frames_after_current": FRAMES_AFTER_CURRENT,
            "sequential_context_previous_frames":
                SEQUENTIAL_CONTEXT_PREVIOUS_FRAMES
        },
        "frame_result_counts": {
            "total_saved": len(analyzed_frames),
            "succeeded": len(
                [
                    item
                    for item in analyzed_frames
                    if item.get("status") == "succeeded"
                ]
            ),
            "failed": len(
                [
                    item
                    for item in analyzed_frames
                    if item.get("status") == "failed"
                ]
            )
        },
        "analyzed_frames": analyzed_frames
    }


def _save_partial_rag_output(
    storage: StorageService,
    video_id: str,
    manifest: dict,
    frame_results: list
):

    partial_document = _build_partial_rag_document(
        video_id=video_id,
        manifest=manifest,
        frame_results=frame_results
    )

    storage.upload_json(
        RAG_DATABASE_CONTAINER,
        f"{video_id}.partial.json",
        partial_document
    )


def _all_frames_completed(
    results_by_index: dict,
    total_frames: int
) -> bool:

    expected = set(range(total_frames))
    actual = set(int(index) for index in results_by_index.keys())

    return expected.issubset(actual)


def _missing_frame_indices(
    results_by_index: dict,
    total_frames: int
) -> list:

    expected = set(range(total_frames))
    actual = set(int(index) for index in results_by_index.keys())

    return sorted(list(expected - actual))


# ==================================================
# SEGMENT ANALYSIS
# ==================================================

def analyze_video_segments(
    video_id: str
):

    invocation_start = time.monotonic()

    logging.info(
        f"SEGMENT START video_id={video_id}"
    )

    storage = StorageService()
    queue_service = QueueService()
    checkpoint_service = CheckpointService(storage)

    try:

        # ==================================================
        # LOAD MANIFEST
        # ==================================================

        manifest = storage.load_manifest(video_id)

        logging.info(
            f"SEGMENT MANIFEST LOADED video_id={video_id} "
            f"status={manifest.get('status')} "
            f"segment_complete={manifest.get('segment_analysis_complete')}"
        )

        if manifest.get("segment_analysis_complete", False):

            logging.info(
                f"Segment analysis already complete for {video_id}"
            )

            if not manifest.get("aggregation_complete", False):

                logging.info(
                    f"Aggregation incomplete. Requeueing aggregation "
                    f"for {video_id}"
                )

                queue_service.send_message(
                    AGGREGATION_QUEUE,
                    {
                        "video_id": video_id
                    }
                )

            return

        storage.update_manifest(
            video_id,
            {
                "segment_analysis_started": True,
                "segment_analysis_complete": False,
                "status": STATUS_SEGMENT_ANALYSIS,
                "processing_error": "",
                "last_updated_utc": _utc_now()
            }
        )

        manifest = storage.load_manifest(video_id)

        # ==================================================
        # LOAD FRAME MANIFEST
        # ==================================================

        frame_manifest = storage.download_json(
            EXTRACTED_FRAMES_CONTAINER,
            f"{video_id}/frame_manifest.json"
        )

        frames = frame_manifest.get("frames", [])
        total_frames = len(frames)

        logging.info(
            f"FRAME_MANIFEST LOADED video_id={video_id} "
            f"total_frames={total_frames}"
        )

        if total_frames == 0:
            raise RuntimeError(
                f"No frames found in frame manifest for {video_id}"
            )

        # ==================================================
        # LOAD INSIGHTS / TRANSCRIPT
        # ==================================================

        insights_blob = (
            manifest.get("insights_blob", "")
            .replace("video-indexer-outputs/", "")
        )

        if not insights_blob:
            raise RuntimeError(
                f"Manifest does not contain insights_blob for {video_id}"
            )

        insights = storage.download_json(
            VIDEO_INDEXER_OUTPUTS_CONTAINER,
            insights_blob
        )

        transcript_entries = (
            insights
            .get("videos", [{}])[0]
            .get("insights", {})
            .get("transcript", [])
        )

        logging.info(
            f"INSIGHTS LOADED video_id={video_id} "
            f"transcript_entries={len(transcript_entries)}"
        )

        # ==================================================
        # LOAD EXISTING FRAME CHECKPOINTS
        # ==================================================

        results_by_index = checkpoint_service.load_frame_results_map(
            video_id
        )

        logging.info(
            f"RESUME STATE video_id={video_id} "
            f"existing_frame_checkpoints={len(results_by_index)} "
            f"total_frames={total_frames}"
        )

        if _all_frames_completed(results_by_index, total_frames):

            logging.info(
                f"All frame checkpoints already exist for {video_id}. "
                f"Marking segment complete and queueing aggregation."
            )

            all_results = checkpoint_service.load_all_frame_results(video_id)

            failed_count = len(
                [
                    item
                    for item in all_results
                    if item.get("status") == "failed"
                ]
            )

            succeeded_count = len(
                [
                    item
                    for item in all_results
                    if item.get("status") == "succeeded"
                ]
            )

            storage.update_manifest(
                video_id,
                {
                    "segment_analysis_started": False,
                    "segment_analysis_complete": True,
                    "status": STATUS_SEGMENT_ANALYSIS_COMPLETE,
                    "segment_frames_expected": total_frames,
                    "segment_frames_completed_or_failed": len(all_results),
                    "segment_frames_succeeded": succeeded_count,
                    "segment_frames_failed": failed_count,
                    "processing_error": "",
                    "last_updated_utc": _utc_now()
                }
            )

            queue_service.send_message(
                AGGREGATION_QUEUE,
                {
                    "video_id": video_id
                }
            )

            logging.info(
                f"AGGREGATION QUEUED video_id={video_id}"
            )

            return

        checkpoint_service.save_progress(
            video_id,
            {
                "video_id": video_id,
                "status": "segment_analysis_running",
                "total_frames": total_frames,
                "completed_or_failed_frames": len(results_by_index),
                "last_frame_index": (
                    max(results_by_index.keys())
                    if results_by_index
                    else -1
                ),
                "timestamp_seconds": 0
            }
        )

        # ==================================================
        # CREATE OPENAI CLIENT
        # ==================================================

        openai_service = OpenAIService()

        # ==================================================
        # PROCESS A SAFE BATCH ONLY
        # ==================================================

        frames_processed_this_invocation = 0

        for frame_index, frame in enumerate(frames):

            elapsed_seconds = time.monotonic() - invocation_start

            if elapsed_seconds >= MAX_SEGMENT_WORKER_SECONDS:

                logging.warning(
                    f"SEGMENT SAFE STOP by time video_id={video_id} "
                    f"elapsed_seconds={elapsed_seconds:.2f}"
                )

                break

            if frames_processed_this_invocation >= SEGMENT_BATCH_SIZE_FRAMES:

                logging.info(
                    f"SEGMENT SAFE STOP by batch size video_id={video_id} "
                    f"batch_size={SEGMENT_BATCH_SIZE_FRAMES}"
                )

                break

            if frame_index in results_by_index:

                logging.info(
                    f"FRAME SKIP existing checkpoint video_id={video_id} "
                    f"frame_index={frame_index}"
                )

                continue

            timestamp = frame.get("timestamp_seconds")
            frame_path = frame.get("blob_path")

            logging.info(
                f"FRAME START video_id={video_id} "
                f"frame_index={frame_index} "
                f"timestamp={timestamp} "
                f"frame_path={frame_path}"
            )

            checkpoint_service.save_progress(
                video_id,
                {
                    "video_id": video_id,
                    "status": "frame_started",
                    "total_frames": total_frames,
                    "completed_or_failed_frames": len(results_by_index),
                    "last_frame_index": frame_index,
                    "timestamp_seconds": timestamp
                }
            )

            transcript_context = ""
            previous_context = ""
            description = ""
            frame_status = "succeeded"
            frame_error = ""

            try:

                transcript_context = build_transcript_context(
                    transcript_entries,
                    timestamp
                )

                logging.info(
                    f"TRANSCRIPT BUILT video_id={video_id} "
                    f"frame_index={frame_index} "
                    f"chars={len(transcript_context)}"
                )

                previous_buffer = _build_previous_buffer_from_results(
                    results_by_index,
                    frame_index
                )

                previous_context = build_previous_context(previous_buffer)

                logging.info(
                    f"PREVIOUS CONTEXT BUILT video_id={video_id} "
                    f"frame_index={frame_index} "
                    f"chars={len(previous_context)}"
                )

                image_context = build_image_context(
                    frame_manifest,
                    frame_index
                )

                base64_lengths = [
                    len(_safe_text(item.get("base64_image")))
                    for item in image_context
                ]

                logging.info(
                    f"IMAGE CONTEXT BUILT video_id={video_id} "
                    f"frame_index={frame_index} "
                    f"image_count={len(image_context)} "
                    f"base64_lengths={base64_lengths}"
                )

                logging.info(
                    f"OPENAI START video_id={video_id} "
                    f"frame_index={frame_index}"
                )

                description = openai_service.analyze_frame(
                    transcript_context=transcript_context,
                    previous_context=previous_context,
                    image_sequence=image_context
                )

                logging.info(
                    f"OPENAI SUCCESS video_id={video_id} "
                    f"frame_index={frame_index} "
                    f"description_chars={len(description)}"
                )

            except Exception as frame_ex:

                frame_status = "failed"
                frame_error = str(frame_ex)

                description = (
                    "Error: Frame analysis failed. "
                    f"{frame_error}"
                )

                logging.exception(
                    f"FRAME FAILED video_id={video_id} "
                    f"frame_index={frame_index} "
                    f"timestamp={timestamp} "
                    f"error={frame_error}"
                )

            frame_result = {
                "video_id": video_id,
                "frame_index": frame_index,
                "timestamp_seconds": timestamp,
                "frame_path": frame_path,
                "speech_context": transcript_context,
                "previous_context_used": previous_context,
                "ai_visual_description": description,
                "combined_context": (
                    transcript_context
                    +
                    "\n\n"
                    +
                    description
                ),
                "status": frame_status,
                "error": frame_error,
                "created_utc": _utc_now()
            }

            checkpoint_service.save_frame_result(
                video_id,
                frame_index,
                frame_result
            )

            results_by_index[frame_index] = frame_result

            frames_processed_this_invocation += 1

            logging.info(
                f"FRAME CHECKPOINT SAVED video_id={video_id} "
                f"frame_index={frame_index} "
                f"status={frame_status} "
                f"completed_or_failed={len(results_by_index)}/{total_frames}"
            )

            if frame_status == "failed" and FRAME_FAILURE_MODE == "fail_fast":
                raise RuntimeError(
                    f"Frame {frame_index} failed and "
                    f"FRAME_FAILURE_MODE=fail_fast. Error: {frame_error}"
                )

            if frame_index % CHECKPOINT_INTERVAL_FRAMES == 0:

                checkpoint_service.save_progress(
                    video_id,
                    {
                        "video_id": video_id,
                        "status": "segment_analysis_running",
                        "total_frames": total_frames,
                        "completed_or_failed_frames": len(results_by_index),
                        "last_frame_index": frame_index,
                        "timestamp_seconds": timestamp
                    }
                )

            if frame_index % PARTIAL_RAG_SAVE_INTERVAL_FRAMES == 0:

                _save_partial_rag_output(
                    storage,
                    video_id,
                    manifest,
                    list(results_by_index.values())
                )

                logging.info(
                    f"PARTIAL RAG SAVED video_id={video_id} "
                    f"frame_index={frame_index}"
                )

            if frame_index % SAVE_MANIFEST_INTERVAL_FRAMES == 0:

                storage.update_manifest(
                    video_id,
                    {
                        "last_segment_frame_index": frame_index,
                        "segment_frames_completed_or_failed":
                            len(results_by_index),
                        "segment_frames_expected": total_frames,
                        "last_updated_utc": _utc_now()
                    }
                )

        # ==================================================
        # AFTER BATCH: COMPLETE OR REQUEUE
        # ==================================================

        all_results = checkpoint_service.load_all_frame_results(video_id)
        results_by_index = checkpoint_service.load_frame_results_map(video_id)

        completed_count = len(results_by_index)

        _save_partial_rag_output(
            storage,
            video_id,
            manifest,
            all_results
        )

        missing_indices = _missing_frame_indices(
            results_by_index,
            total_frames
        )

        if missing_indices:

            logging.info(
                f"SEGMENT PARTIAL COMPLETE video_id={video_id} "
                f"completed={completed_count}/{total_frames} "
                f"next_missing={missing_indices[0]}"
            )

            storage.update_manifest(
                video_id,
                {
                    "segment_analysis_started": False,
                    "segment_analysis_complete": False,
                    "status": STATUS_SEGMENT_ANALYSIS,
                    "segment_frames_expected": total_frames,
                    "segment_frames_completed_or_failed": completed_count,
                    "next_segment_frame_index": missing_indices[0],
                    "processing_error": "",
                    "last_updated_utc": _utc_now()
                }
            )

            checkpoint_service.save_progress(
                video_id,
                {
                    "video_id": video_id,
                    "status": "segment_analysis_requeued",
                    "total_frames": total_frames,
                    "completed_or_failed_frames": completed_count,
                    "last_frame_index": (
                        max(results_by_index.keys())
                        if results_by_index
                        else -1
                    ),
                    "next_missing_frame_index": missing_indices[0]
                }
            )

            queue_service.send_message(
                SEGMENT_ANALYSIS_QUEUE,
                {
                    "video_id": video_id
                }
            )

            logging.info(
                f"SEGMENT REQUEUED video_id={video_id} "
                f"completed={completed_count}/{total_frames}"
            )

            return

        # ==================================================
        # ALL FRAMES COMPLETE
        # ==================================================

        failed_count = len(
            [
                item
                for item in all_results
                if item.get("status") == "failed"
            ]
        )

        succeeded_count = len(
            [
                item
                for item in all_results
                if item.get("status") == "succeeded"
            ]
        )

        storage.update_manifest(
            video_id,
            {
                "segment_analysis_started": False,
                "segment_analysis_complete": True,
                "status": STATUS_SEGMENT_ANALYSIS_COMPLETE,
                "segment_frames_expected": total_frames,
                "segment_frames_completed_or_failed": len(all_results),
                "segment_frames_succeeded": succeeded_count,
                "segment_frames_failed": failed_count,
                "processing_error": "",
                "last_updated_utc": _utc_now()
            }
        )

        checkpoint_service.save_progress(
            video_id,
            {
                "video_id": video_id,
                "status": STATUS_SEGMENT_ANALYSIS_COMPLETE,
                "total_frames": total_frames,
                "completed_or_failed_frames": len(all_results),
                "last_frame_index": total_frames - 1,
                "timestamp_seconds": frames[-1].get(
                    "timestamp_seconds",
                    0
                )
            }
        )

        queue_service.send_message(
            AGGREGATION_QUEUE,
            {
                "video_id": video_id
            }
        )

        logging.info(
            f"AGGREGATION QUEUED video_id={video_id}"
        )

    except Exception as ex:

        logging.exception(
            f"Segment analysis failed for {video_id}: {ex}"
        )

        try:

            storage.update_manifest(
                video_id,
                {
                    "segment_analysis_started": False,
                    "segment_analysis_complete": False,
                    "processing_error": str(ex),
                    "status": STATUS_SEGMENT_ANALYSIS_FAILED,
                    "last_updated_utc": _utc_now()
                }
            )

        except Exception:

            logging.exception(
                f"Unable to update failed manifest for {video_id}"
            )

        raise