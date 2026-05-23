import json
import os
import re
from pathlib import Path

from azure.storage.blob import BlobServiceClient


RAG_CONTAINER = "rag-database-json"
INSIGHTS_CONTAINER = "video-indexer-outputs"
CHECKPOINTS_CONTAINER = "processing-checkpoints"
MANIFESTS_CONTAINER = "processing-manifests"


def load_connection_string() -> str:

    value = os.getenv("AzureWebJobsStorage")

    if value:
        return value

    local_settings = Path("local.settings.json")

    if local_settings.exists():

        data = json.loads(
            local_settings.read_text(encoding="utf-8")
        )

        value = (
            data
            .get("Values", {})
            .get("AzureWebJobsStorage")
        )

        if value:
            return value

    raise RuntimeError(
        "AzureWebJobsStorage not found in environment "
        "or local.settings.json."
    )


def sanitize_name(value: str) -> str:

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

    return cleaned or "unknown_video"


def sanitize_json_object(data):

    username_replacement = "AFO"
    account_replacement = "AFO_ACCOUNT"

    replacements = {
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

        output = {}

        for key, value in data.items():

            if key in replacements:
                output[key] = replacements[key]
            else:
                output[key] = sanitize_json_object(value)

        return output

    if isinstance(data, list):

        return [
            sanitize_json_object(item)
            for item in data
        ]

    return data


def download_json(container_client, blob_name):

    blob_client = container_client.get_blob_client(blob_name)

    raw = blob_client.download_blob().readall()

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    return json.loads(raw)


def upload_json(container_client, blob_name, data):

    blob_client = container_client.get_blob_client(blob_name)

    blob_client.upload_blob(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        overwrite=True
    )


def cleanup_rag_outputs(blob_service):

    container = blob_service.get_container_client(RAG_CONTAINER)

    blobs = [
        blob.name
        for blob in container.list_blobs()
    ]

    friendly_blobs = [
        name
        for name in blobs
        if "__" in name and name.endswith(".json")
    ]

    friendly_ids = set()

    for name in friendly_blobs:

        stem = name[:-5]

        video_id = stem.split("__")[-1]

        if video_id:
            friendly_ids.add(video_id)

    deleted_partials = []
    deleted_id_duplicates = []

    for name in blobs:

        if name.endswith(".partial.json"):

            container.delete_blob(name)

            deleted_partials.append(name)

            continue

        if not name.endswith(".json"):
            continue

        if "__" in name:
            continue

        video_id = name[:-5]

        if video_id in friendly_ids:

            container.delete_blob(name)

            deleted_id_duplicates.append(name)

    print("Deleted partial RAG files:")
    for item in deleted_partials:
        print("  " + item)

    print("Deleted ID-only duplicate RAG files:")
    for item in deleted_id_duplicates:
        print("  " + item)


def sanitize_existing_insights(blob_service):

    container = blob_service.get_container_client(INSIGHTS_CONTAINER)

    blobs = [
        blob.name
        for blob in container.list_blobs()
        if blob.name.endswith("/insights.json")
    ]

    sanitized_count = 0

    for blob_name in blobs:

        data = download_json(container, blob_name)

        sanitized = sanitize_json_object(data)

        if sanitized != data:

            upload_json(container, blob_name, sanitized)

            sanitized_count += 1

            print(f"Sanitized insights: {blob_name}")

    print(f"Sanitized insights files: {sanitized_count}")


def main():

    connection_string = load_connection_string()

    blob_service = BlobServiceClient.from_connection_string(
        connection_string
    )

    cleanup_rag_outputs(blob_service)

    sanitize_existing_insights(blob_service)


if __name__ == "__main__":
    main()