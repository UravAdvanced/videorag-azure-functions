import json
import logging
import os
from datetime import datetime, timezone

import azure.functions as func

from modules.storage.sas_helper import (
    generate_blob_sas_url
)

from modules.video_indexer.video_indexer_callback import (
    process_callback
)

from modules.video_indexer.trigger_vi import (
    process_uploaded_video
)

from modules.video_indexer.process_vi_output import (
    process_vi_output
)

from modules.frame_extraction.frame_extraction_worker import (
    extract_frames
)

from modules.aggregation.aggregation_worker import (
    aggregate_video
)

from modules.segment_analysis.segment_analysis_worker import (
    analyze_video_segments
)

from modules.config import (
    FRAME_EXTRACTION_QUEUE,
    SEGMENT_ANALYSIS_QUEUE,
    AGGREGATION_QUEUE
)


app = func.FunctionApp(
    http_auth_level=func.AuthLevel.ANONYMOUS
)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _json_response(
    payload: dict,
    status_code: int = 200
) -> func.HttpResponse:

    return func.HttpResponse(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False
        ),
        mimetype="application/json",
        status_code=status_code
    )


def _safe_decode_body(
    req: func.HttpRequest
) -> str:

    try:

        return req.get_body().decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:

        return ""


def _try_get_json(
    req: func.HttpRequest
):

    try:

        return req.get_json()

    except Exception:

        return None


def _resolve_callback_video_id(
    req: func.HttpRequest,
    payload
) -> str:

    candidate_keys = [
        "id",
        "videoId",
        "video_id",
        "videoID",
        "VideoId",
        "video"
    ]

    # ----------------------------------------------
    # QUERY PARAMS FIRST
    # ----------------------------------------------

    for key in candidate_keys:

        value = req.params.get(
            key
        )

        if value:

            return str(
                value
            ).strip()

    # ----------------------------------------------
    # JSON BODY
    # ----------------------------------------------

    if isinstance(
        payload,
        dict
    ):

        for key in candidate_keys:

            value = payload.get(
                key
            )

            if value:

                return str(
                    value
                ).strip()

        # Some callback systems wrap data
        for wrapper_key in [
            "data",
            "payload",
            "video"
        ]:

            wrapped = payload.get(
                wrapper_key
            )

            if isinstance(
                wrapped,
                dict
            ):

                for key in candidate_keys:

                    value = wrapped.get(
                        key
                    )

                    if value:

                        return str(
                            value
                        ).strip()

    return ""


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route(
    route="health",
    methods=["GET"]
)
def health(
    req: func.HttpRequest
) -> func.HttpResponse:

    payload = {
        "status": "healthy",
        "service": "VideoRAG Automated Pipeline",
        "utc_time": datetime.now(
            timezone.utc
        ).isoformat()
    }

    return _json_response(
        payload,
        status_code=200
    )


# --------------------------------------------------
# VIDEO INDEXER CALLBACK
# --------------------------------------------------

@app.route(
    route="video_indexer_callback",
    methods=[
        "GET",
        "POST"
    ]
)
def video_indexer_callback(
    req: func.HttpRequest
) -> func.HttpResponse:

    try:

        raw_body = _safe_decode_body(
            req
        )

        payload = _try_get_json(
            req
        )

        query_params = {
            key: req.params.get(
                key
            )
            for key in req.params.keys()
        }

        logging.warning(
            f"VIDEO INDEXER CALLBACK METHOD = {req.method}"
        )

        logging.warning(
            f"VIDEO INDEXER CALLBACK QUERY = {query_params}"
        )

        logging.warning(
            f"VIDEO INDEXER CALLBACK RAW BODY = {raw_body}"
        )

        logging.warning(
            f"VIDEO INDEXER CALLBACK JSON PAYLOAD = {payload}"
        )

        video_id = _resolve_callback_video_id(
            req,
            payload
        )

        logging.warning(
            f"VIDEO INDEXER CALLBACK RESOLVED VIDEO ID = {video_id}"
        )

        if not video_id:

            logging.error(
                "No video id found in Video Indexer callback."
            )

            return _json_response(
                {
                    "status": "error",
                    "message": "Missing video id",
                    "method": req.method,
                    "query": query_params,
                    "raw_body": raw_body
                },
                status_code=400
            )

        process_callback(
            video_id
        )

        logging.info(
            f"Callback processing completed for {video_id}"
        )

        return _json_response(
            {
                "status": "ok",
                "video_id": video_id
            },
            status_code=200
        )

    except Exception as ex:

        logging.exception(
            f"VideoIndexerCallback failed: {ex}"
        )

        return _json_response(
            {
                "status": "error",
                "message": str(
                    ex
                )
            },
            status_code=500
        )


# --------------------------------------------------
# PROCESS VIDEO INDEXER OUTPUT WORKER
# --------------------------------------------------

@app.queue_trigger(
    arg_name="msg",
    queue_name="process-vi-output-queue",
    connection="AzureWebJobsStorage"
)
def process_vi_output_worker(
    msg: func.QueueMessage
):

    try:

        raw_body = msg.get_body()

        logging.info(
            f"PROCESS_VI_OUTPUT RAW TYPE = {type(raw_body)}"
        )

        logging.info(
            f"PROCESS_VI_OUTPUT RAW BODY = {raw_body}"
        )

        if isinstance(
            raw_body,
            bytes
        ):

            raw_body = raw_body.decode(
                "utf-8"
            )

        payload = json.loads(
            raw_body
        )

        logging.info(
            f"PROCESS_VI_OUTPUT PAYLOAD = {payload}"
        )

        video_id = payload[
            "video_id"
        ]

        logging.info(
            f"Starting ProcessVIOutput for {video_id}"
        )

        process_vi_output(
            video_id
        )

        logging.info(
            f"ProcessVIOutput completed for {video_id}"
        )

    except Exception:

        logging.exception(
            "ProcessVIOutput failed"
        )

        raise


# --------------------------------------------------
# TRIGGER VIDEO INDEXER
# --------------------------------------------------

@app.blob_trigger(
    arg_name="inputblob",
    path="input-videos/{name}",
    connection="AzureWebJobsStorage"
)
def trigger_vi(
    inputblob: func.InputStream
):

    try:

        blob_name = (
            inputblob.name
            .replace(
                "input-videos/",
                ""
            )
        )

        logging.info(
            f"Processing upload: {blob_name}"
        )

        sas_url = generate_blob_sas_url(
            container_name="input-videos",
            blob_name=blob_name,
            expiry_hours=24
        )

        callback_url = os.getenv(
            "VIDEO_INDEXER_CALLBACK_URL",
            ""
        )

        logging.warning(
            f"TriggerVI callback_url_present={bool(callback_url)}"
        )

        logging.warning(
            f"TriggerVI callback_url={callback_url}"
        )

        manifest = process_uploaded_video(
            blob_name=blob_name,
            sas_url=sas_url,
            callback_url=callback_url
        )

        logging.info(
            f"Video submitted to Video Indexer. "
            f"Video ID: {manifest['video_id']}"
        )

    except Exception:

        logging.exception(
            "TriggerVI failed"
        )

        raise


# --------------------------------------------------
# FRAME EXTRACTION WORKER
# --------------------------------------------------

@app.queue_trigger(
    arg_name="msg",
    queue_name=FRAME_EXTRACTION_QUEUE,
    connection="AzureWebJobsStorage"
)
def frame_extraction_worker(
    msg: func.QueueMessage
):

    try:

        raw_body = msg.get_body().decode(
            "utf-8"
        )

        logging.info(
            f"FRAME EXTRACTION RAW QUEUE BODY: {raw_body}"
        )

        payload = json.loads(
            raw_body
        )

        video_id = payload[
            "video_id"
        ]

        logging.info(
            f"Starting frame extraction for {video_id}"
        )

        extract_frames(
            video_id
        )

    except Exception:

        logging.exception(
            "FrameExtractionWorker failed"
        )

        raise


# --------------------------------------------------
# SEGMENT ANALYSIS WORKER
# --------------------------------------------------

@app.queue_trigger(
    arg_name="msg",
    queue_name=SEGMENT_ANALYSIS_QUEUE,
    connection="AzureWebJobsStorage"
)
def segment_analysis_worker(
    msg: func.QueueMessage
):

    try:

        raw_body = msg.get_body().decode(
            "utf-8"
        )

        logging.info(
            f"SEGMENT ANALYSIS RAW QUEUE BODY: {raw_body}"
        )

        payload = json.loads(
            raw_body
        )

        video_id = payload[
            "video_id"
        ]

        logging.info(
            f"Starting segment analysis for {video_id}"
        )

        analyze_video_segments(
            video_id
        )

        logging.info(
            f"Segment analysis completed for {video_id}"
        )

    except Exception:

        logging.exception(
            "SegmentAnalysisWorker failed"
        )

        raise


# --------------------------------------------------
# AGGREGATION WORKER
# --------------------------------------------------

@app.queue_trigger(
    arg_name="msg",
    queue_name=AGGREGATION_QUEUE,
    connection="AzureWebJobsStorage"
)
def aggregation_worker(
    msg: func.QueueMessage
):

    try:

        raw_body = msg.get_body().decode(
            "utf-8"
        )

        logging.info(
            f"AGGREGATION RAW QUEUE BODY: {raw_body}"
        )

        payload = json.loads(
            raw_body
        )

        video_id = payload[
            "video_id"
        ]

        logging.info(
            f"Starting aggregation for {video_id}"
        )

        aggregate_video(
            video_id
        )

        logging.info(
            f"Aggregation completed for {video_id}"
        )

    except Exception:

        logging.exception(
            "AggregationWorker failed"
        )

        raise