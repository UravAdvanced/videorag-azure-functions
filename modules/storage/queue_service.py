import json
import os

from azure.storage.queue import (
    QueueClient
)


class QueueService:

    def __init__(self):

        self.connection_string = os.getenv(
            "AzureWebJobsStorage"
        )

    def send_message(
        self,
        queue_name: str,
        message: dict
    ):

        queue_client = (
            QueueClient.from_connection_string(
                self.connection_string,
                queue_name
            )
        )

        queue_client.send_message(
            json.dumps(
                message
            )
        )

    def delete_message(
        self,
        queue_name: str,
        message_id: str,
        pop_receipt: str
    ):

        queue_client = (
            QueueClient.from_connection_string(
                self.connection_string,
                queue_name
            )
        )

        queue_client.delete_message(
            message_id,
            pop_receipt
        )