import os
from datetime import datetime, timedelta

from azure.storage.blob import (
    BlobServiceClient,
    BlobSasPermissions,
    generate_blob_sas
)


def generate_blob_sas_url(
    container_name: str,
    blob_name: str,
    expiry_hours: int = 24
):

    connection_string = os.getenv(
        "AzureWebJobsStorage"
    )

    blob_service_client = (
        BlobServiceClient
        .from_connection_string(
            connection_string
        )
    )

    account_name = (
        blob_service_client
        .account_name
    )

    account_key = None

    for part in connection_string.split(";"):

        if part.startswith(
            "AccountKey="
        ):
            account_key = (
                part.split(
                    "=",
                    1
                )[1]
            )
            break

    if not account_key:

        raise RuntimeError(
            "Unable to locate "
            "AccountKey in "
            "AzureWebJobsStorage"
        )

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(
            read=True
        ),
        expiry=(
            datetime.utcnow()
            +
            timedelta(
                hours=expiry_hours
            )
        )
    )

    return (
        f"https://{account_name}"
        f".blob.core.windows.net/"
        f"{container_name}/"
        f"{blob_name}"
        f"?{sas_token}"
    )