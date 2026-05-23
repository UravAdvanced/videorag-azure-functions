# --------------------------------------------------
# IMPORTS
# --------------------------------------------------

import json
import logging
import os

from datetime import (
    datetime,
    timezone
)

from pathlib import Path

from azure.core.exceptions import (
    ResourceNotFoundError
)

from azure.storage.blob import (
    BlobServiceClient,
    ContentSettings
)

from modules.config import (
    PROCESSING_MANIFESTS_CONTAINER,
    PROCESSING_CHECKPOINTS_CONTAINER
)


# --------------------------------------------------
# STORAGE SERVICE
# --------------------------------------------------

class StorageService:

    def __init__(self):

        connection_string = os.getenv(
            "AzureWebJobsStorage"
        )

        if not connection_string:

            raise RuntimeError(
                "AzureWebJobsStorage is not configured."
            )

        self.blob_service_client = (
            BlobServiceClient
            .from_connection_string(
                connection_string
            )
        )

    # --------------------------------------------------
    # JSON OPERATIONS
    # --------------------------------------------------

    def upload_json(
        self,
        container_name: str,
        blob_name: str,
        data: dict
    ):

        logging.info(
            f"Uploading JSON: "
            f"{container_name}/{blob_name}"
        )

        blob_client = (
            self.blob_service_client
            .get_blob_client(
                container=container_name,
                blob=blob_name
            )
        )

        payload = json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        )

        blob_client.upload_blob(
            payload,
            overwrite=True,
            content_settings=ContentSettings(
                content_type=(
                    "application/json; "
                    "charset=utf-8"
                )
            )
        )

    def download_json(
        self,
        container_name: str,
        blob_name: str
    ):

        logging.info(
            f"Downloading JSON: "
            f"{container_name}/{blob_name}"
        )

        blob_client = (
            self.blob_service_client
            .get_blob_client(
                container=container_name,
                blob=blob_name
            )
        )

        content = (
            blob_client
            .download_blob()
            .readall()
        )

        if isinstance(
            content,
            bytes
        ):

            content = content.decode(
                "utf-8"
            )

        return json.loads(
            content
        )

    def download_json_if_exists(
        self,
        container_name: str,
        blob_name: str
    ):

        if not self.blob_exists(
            container_name,
            blob_name
        ):

            return None

        return self.download_json(
            container_name,
            blob_name
        )

    # --------------------------------------------------
    # FILE OPERATIONS
    # --------------------------------------------------

    def upload_file(
        self,
        container_name: str,
        blob_name: str,
        local_file_path: str
    ):

        logging.info(
            f"Uploading file: "
            f"{container_name}/{blob_name}"
        )

        blob_client = (
            self.blob_service_client
            .get_blob_client(
                container=container_name,
                blob=blob_name
            )
        )

        with open(
            local_file_path,
            "rb"
        ) as file_handle:

            blob_client.upload_blob(
                file_handle,
                overwrite=True
            )

    def download_blob_to_file(
        self,
        container_name: str,
        blob_name: str,
        local_file_path: str
    ):

        logging.info(
            f"Downloading blob: "
            f"{container_name}/{blob_name}"
        )

        Path(
            local_file_path
        ).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        blob_client = (
            self.blob_service_client
            .get_blob_client(
                container=container_name,
                blob=blob_name
            )
        )

        with open(
            local_file_path,
            "wb"
        ) as file_handle:

            file_handle.write(
                blob_client
                .download_blob()
                .readall()
            )

    def download_blob_bytes(
        self,
        container_name: str,
        blob_name: str
    ) -> bytes:

        logging.info(
            f"Downloading bytes: "
            f"{container_name}/{blob_name}"
        )

        blob_client = (
            self.blob_service_client
            .get_blob_client(
                container=container_name,
                blob=blob_name
            )
        )

        return (
            blob_client
            .download_blob()
            .readall()
        )

    # --------------------------------------------------
    # GENERAL HELPERS
    # --------------------------------------------------

    def blob_exists(
        self,
        container_name: str,
        blob_name: str
    ) -> bool:

        blob_client = (
            self.blob_service_client
            .get_blob_client(
                container=container_name,
                blob=blob_name
            )
        )

        try:

            return blob_client.exists()

        except ResourceNotFoundError:

            return False

    def delete_blob(
        self,
        container_name: str,
        blob_name: str
    ):

        logging.info(
            f"Deleting blob: "
            f"{container_name}/{blob_name}"
        )

        blob_client = (
            self.blob_service_client
            .get_blob_client(
                container=container_name,
                blob=blob_name
            )
        )

        if blob_client.exists():

            blob_client.delete_blob()

    def delete_blobs_with_prefix(
        self,
        container_name: str,
        prefix: str
    ):

        logging.info(
            f"Deleting blobs under prefix: "
            f"{container_name}/{prefix}"
        )

        container_client = (
            self.blob_service_client
            .get_container_client(
                container_name
            )
        )

        deleted_count = 0

        for blob in container_client.list_blobs(
            name_starts_with=prefix
        ):

            container_client.delete_blob(
                blob.name
            )

            deleted_count += 1

        logging.info(
            f"Deleted {deleted_count} blobs "
            f"from {container_name}/{prefix}"
        )

        return deleted_count

    def list_blobs(
        self,
        container_name: str,
        prefix: str = ""
    ):

        container_client = (
            self.blob_service_client
            .get_container_client(
                container_name
            )
        )

        return [
            blob.name
            for blob in
            container_client.list_blobs(
                name_starts_with=prefix
            )
        ]

    # --------------------------------------------------
    # MANIFEST OPERATIONS
    # --------------------------------------------------

    def save_manifest(
        self,
        video_id: str,
        manifest_data: dict
    ):

        self.upload_json(
            PROCESSING_MANIFESTS_CONTAINER,
            f"{video_id}.json",
            manifest_data
        )

    def load_manifest(
        self,
        video_id: str
    ):

        return self.download_json(
            PROCESSING_MANIFESTS_CONTAINER,
            f"{video_id}.json"
        )

    def manifest_exists(
        self,
        video_id: str
    ) -> bool:

        return self.blob_exists(
            PROCESSING_MANIFESTS_CONTAINER,
            f"{video_id}.json"
        )

    def update_manifest(
        self,
        video_id: str,
        updates: dict
    ):

        manifest = (
            self.load_manifest(
                video_id
            )
        )

        updates[
            "last_updated_utc"
        ] = datetime.now(
            timezone.utc
        ).isoformat()

        manifest.update(
            updates
        )

        self.save_manifest(
            video_id,
            manifest
        )

        return manifest

    # --------------------------------------------------
    # FRAME MANIFESTS
    # --------------------------------------------------

    def save_frame_manifest(
        self,
        video_id: str,
        frame_manifest: dict,
        container_name: str
    ):

        self.upload_json(
            container_name,
            f"{video_id}/frame_manifest.json",
            frame_manifest
        )

    def load_frame_manifest(
        self,
        video_id: str,
        container_name: str
    ):

        return self.download_json(
            container_name,
            f"{video_id}/frame_manifest.json"
        )

    # --------------------------------------------------
    # CHECKPOINT OPERATIONS
    # --------------------------------------------------

    def save_checkpoint(
        self,
        video_id: str,
        segment_id: int,
        checkpoint_data: dict
    ):

        self.upload_json(
            PROCESSING_CHECKPOINTS_CONTAINER,
            f"{video_id}/segment_{segment_id}.json",
            checkpoint_data
        )

    def load_checkpoint(
        self,
        video_id: str,
        segment_id: int
    ):

        blob_name = (
            f"{video_id}/"
            f"segment_{segment_id}.json"
        )

        if not self.blob_exists(
            PROCESSING_CHECKPOINTS_CONTAINER,
            blob_name
        ):

            return None

        return self.download_json(
            PROCESSING_CHECKPOINTS_CONTAINER,
            blob_name
        )