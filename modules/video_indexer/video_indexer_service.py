import logging
import os
import requests

from azure.identity import DefaultAzureCredential


class VideoIndexerService:

    def __init__(self):

        self.subscription_id = os.getenv(
            "AZURE_SUBSCRIPTION_ID"
        )

        self.resource_group = os.getenv(
            "VIDEO_INDEXER_RESOURCE_GROUP"
        )

        self.account_name = os.getenv(
            "VIDEO_INDEXER_ACCOUNT_NAME"
        )

        self.account_id = os.getenv(
            "VIDEO_INDEXER_ACCOUNT_ID"
        )

        self.location = os.getenv(
            "VIDEO_INDEXER_LOCATION",
            "eastus"
        )

        self.request_timeout_seconds = 120

        self._validate_configuration()

    # --------------------------------------------------
    # CONFIG VALIDATION
    # --------------------------------------------------

    def _validate_configuration(self):

        missing = []

        if not self.subscription_id:
            missing.append(
                "AZURE_SUBSCRIPTION_ID"
            )

        if not self.resource_group:
            missing.append(
                "VIDEO_INDEXER_RESOURCE_GROUP"
            )

        if not self.account_name:
            missing.append(
                "VIDEO_INDEXER_ACCOUNT_NAME"
            )

        if not self.account_id:
            missing.append(
                "VIDEO_INDEXER_ACCOUNT_ID"
            )

        if not self.location:
            missing.append(
                "VIDEO_INDEXER_LOCATION"
            )

        if missing:

            raise RuntimeError(
                "Missing Video Indexer configuration: "
                +
                ", ".join(
                    missing
                )
            )

    # --------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------

    def get_access_token(self):

        credential = DefaultAzureCredential()

        arm_token = (
            credential
            .get_token(
                "https://management.azure.com/.default"
            )
            .token
        )

        url = (
            f"https://management.azure.com/"
            f"subscriptions/{self.subscription_id}/"
            f"resourceGroups/{self.resource_group}/"
            f"providers/Microsoft.VideoIndexer/"
            f"accounts/{self.account_name}/"
            f"generateAccessToken"
            f"?api-version=2025-01-01"
        )

        logging.info(
            "Requesting Video Indexer access token."
        )

        response = requests.post(
            url,
            headers={
                "Authorization":
                    f"Bearer {arm_token}",

                "Content-Type":
                    "application/json"
            },
            json={
                "permissionType":
                    "Contributor",

                "scope":
                    "Account"
            },
            timeout=self.request_timeout_seconds
        )

        try:

            response.raise_for_status()

        except Exception:

            logging.error(
                f"Video Indexer token request failed. "
                f"status={response.status_code} "
                f"body={response.text[:1000]}"
            )

            raise

        return response.json()[
            "accessToken"
        ]

    # --------------------------------------------------
    # SUBMIT VIDEO
    # --------------------------------------------------

    def submit_video(
        self,
        video_name: str,
        video_url: str,
        callback_url: str
    ):

        if not video_url:

            raise RuntimeError(
                "video_url is empty."
            )

        if not callback_url:

            raise RuntimeError(
                "callback_url is empty."
            )

        access_token = self.get_access_token()

        url = (
            f"https://api.videoindexer.ai/"
            f"{self.location}/"
            f"Accounts/{self.account_id}/"
            f"Videos"
        )

        logging.warning(
            f"Submitting video to Video Indexer. "
            f"video_name={video_name}, "
            f"location={self.location}, "
            f"account_id_present={bool(self.account_id)}, "
            f"callback_url_present={bool(callback_url)}, "
            f"video_url_present={bool(video_url)}"
        )

        response = requests.post(
            url,
            params={
                "accessToken":
                    access_token,

                "name":
                    video_name,

                "videoUrl":
                    video_url,

                "callbackUrl":
                    callback_url,

                "privacy":
                    "Private"
            },
            timeout=self.request_timeout_seconds
        )

        try:

            response.raise_for_status()

        except Exception:

            logging.error(
                f"Video Indexer submit failed. "
                f"status={response.status_code} "
                f"body={response.text[:1000]}"
            )

            raise

        logging.info(
            f"Video Indexer submit succeeded. "
            f"status={response.status_code}"
        )

        return response.json()

    # --------------------------------------------------
    # VIDEO STATUS
    # --------------------------------------------------

    def get_video_state(
        self,
        video_id: str
    ):

        access_token = self.get_access_token()

        url = (
            f"https://api.videoindexer.ai/"
            f"{self.location}/"
            f"Accounts/{self.account_id}/"
            f"Videos/{video_id}/Index"
        )

        response = requests.get(
            url,
            params={
                "accessToken":
                    access_token
            },
            timeout=self.request_timeout_seconds
        )

        try:

            response.raise_for_status()

        except Exception:

            logging.error(
                f"Video Indexer state request failed. "
                f"video_id={video_id} "
                f"status={response.status_code} "
                f"body={response.text[:1000]}"
            )

            raise

        data = response.json()

        return data.get(
            "state",
            "Unknown"
        )

    # --------------------------------------------------
    # INSIGHTS JSON
    # --------------------------------------------------

    def get_video_insights(
        self,
        video_id: str
    ):

        access_token = self.get_access_token()

        url = (
            f"https://api.videoindexer.ai/"
            f"{self.location}/"
            f"Accounts/{self.account_id}/"
            f"Videos/{video_id}/Index"
        )

        response = requests.get(
            url,
            params={
                "accessToken":
                    access_token
            },
            timeout=self.request_timeout_seconds
        )

        try:

            response.raise_for_status()

        except Exception:

            logging.error(
                f"Video Indexer insights request failed. "
                f"video_id={video_id} "
                f"status={response.status_code} "
                f"body={response.text[:1000]}"
            )

            raise

        return response.json()

    # --------------------------------------------------
    # DOWNLOAD INSIGHTS
    # --------------------------------------------------

    def download_insights_json(
        self,
        video_id: str
    ):

        return self.get_video_insights(
            video_id
        )

    # --------------------------------------------------
    # METADATA HELPERS
    # --------------------------------------------------

    def get_video_duration(
        self,
        video_id: str
    ):

        insights = self.get_video_insights(
            video_id
        )

        try:

            duration = insights.get(
                "durationInSeconds"
            )

            if duration is not None:

                return float(
                    duration
                )

        except Exception:

            pass

        try:

            duration = (
                insights
                .get(
                    "summarizedInsights",
                    {}
                )
                .get(
                    "duration",
                    {}
                )
                .get(
                    "seconds"
                )
            )

            if duration is not None:

                return float(
                    duration
                )

        except Exception:

            pass

        return 0.0

    # --------------------------------------------------
    # PROCESSING CHECK
    # --------------------------------------------------

    def is_processed(
        self,
        video_id: str
    ):

        state = self.get_video_state(
            video_id
        )

        return (
            str(
                state
            )
            .lower()
            ==
            "processed"
        )

    # --------------------------------------------------
    # WAIT FOR PROCESSING
    # --------------------------------------------------

    def wait_for_processing(
        self,
        video_id: str,
        max_attempts: int = 120,
        sleep_seconds: int = 30
    ):

        import time

        for _ in range(
            max_attempts
        ):

            state = self.get_video_state(
                video_id
            )

            logging.info(
                f"Video Indexer state for "
                f"{video_id}: {state}"
            )

            if (
                str(
                    state
                )
                .lower()
                ==
                "processed"
            ):

                return True

            if (
                str(
                    state
                )
                .lower()
                ==
                "failed"
            ):

                return False

            time.sleep(
                sleep_seconds
            )

        return False