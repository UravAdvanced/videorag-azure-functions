# ==================================================
# IMPORTS
# ==================================================

import logging
import time

from openai import (
    AzureOpenAI
)

from modules.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,

    GPT_MAX_RESPONSE_TOKENS,

    MAX_OPENAI_RETRIES,

    OPENAI_RETRY_INITIAL_SECONDS,

    OPENAI_RETRY_MULTIPLIER,

    OPENAI_TIMEOUT_SECONDS,

    OPENAI_CONTENT_FILTER_RETRY,

    MIN_DESCRIPTION_LENGTH
)

from modules.segment_analysis.image_helper import (
    build_frame_label
)


# ==================================================
# OPENAI CLIENT
# ==================================================

class OpenAIService:

    def __init__(self):

        self.client = AzureOpenAI(

            azure_endpoint=
                AZURE_OPENAI_ENDPOINT,

            api_key=
                AZURE_OPENAI_API_KEY,

            api_version=
                "2025-04-01-preview"
        )


    # ==================================================
    # GPT ANALYSIS
    # ==================================================

    def analyze_frame(

        self,

        transcript_context: str,

        previous_context: str,

        image_sequence: list,

        attempt_without_transcript: bool = False
    ):

        system_prompt = (
            "You are analyzing an "
            "educational lecture video.\n\n"

            "You are provided:\n"
            "- Previous context\n"
            "- Transcript context\n"
            "- Sequence of images\n"
            "- Current image\n\n"

            "Focus on the CURRENT FRAME.\n"

            "Use surrounding images "
            "only for temporal context.\n"

            "Identify:\n"
            "- actions\n"
            "- demonstrations\n"
            "- objects\n"
            "- tools\n"
            "- procedures\n\n"

            "Be factual.\n"
            "Do not speculate.\n"

            "If transcript conflicts "
            "with visuals, trust visuals."
        )

        user_content = []

        # ----------------------------------------------
        # PREVIOUS CONTEXT
        # ----------------------------------------------

        if previous_context:

            user_content.append(
                {
                    "type":
                        "text",

                    "text":
                        (
                            "PREVIOUS CONTEXT:\n\n"
                            +
                            previous_context
                        )
                }
            )

        # ----------------------------------------------
        # TRANSCRIPT
        # ----------------------------------------------

        if (
            transcript_context
            and
            not attempt_without_transcript
        ):

            user_content.append(
                {
                    "type":
                        "text",

                    "text":
                        (
                            "TRANSCRIPT:\n\n"
                            +
                            transcript_context
                        )
                }
            )

        # ----------------------------------------------
        # INSTRUCTIONS
        # ----------------------------------------------

        user_content.append(
            {
                "type":
                    "text",

                "text":
                    (
                        "Describe the CURRENT "
                        "FRAME.\n\n"

                        "Explain:\n"

                        "1. What is visible\n"
                        "2. What action occurs\n"
                        "3. Relation to previous "
                        "context\n"
                        "4. Relation to transcript\n"
                        "5. Educational relevance"
                    )
            }
        )

        # ----------------------------------------------
        # IMAGES
        # ----------------------------------------------

        current_index = next(

            i

            for i, img
            in enumerate(
                image_sequence
            )

            if img[
                "is_current"
            ]
        )

        for i, image in enumerate(
            image_sequence
        ):

            label = (
                build_frame_label(
                    current_index,
                    i
                )
            )

            user_content.append(
                {
                    "type":
                        "text",

                    "text":
                        label
                }
            )

            user_content.append(
                {
                    "type":
                        "image_url",

                    "image_url":
                        {
                            "url":
                                (
                                    "data:image/jpeg;base64,"
                                    +
                                    image[
                                        "base64_image"
                                    ]
                                )
                        }
                }
            )

        messages = [

            {
                "role":
                    "system",

                "content":
                    system_prompt
            },

            {
                "role":
                    "user",

                "content":
                    user_content
            }
        ]

        return self._execute_request(
            messages,
            transcript_context,
            previous_context,
            image_sequence
        )

    # ==================================================
    # EXECUTE REQUEST
    # ==================================================

    def _execute_request(

        self,

        messages,

        transcript_context,

        previous_context,

        image_sequence
    ):

        retry_delay = (
            OPENAI_RETRY_INITIAL_SECONDS
        )

        for attempt in range(
            MAX_OPENAI_RETRIES
        ):

            try:

                logging.info(
                    f"OpenAI deployment: "
                    f"{AZURE_OPENAI_DEPLOYMENT_NAME}"
                )

                logging.info(
                    f"OpenAI endpoint: "
                    f"{AZURE_OPENAI_ENDPOINT}"
                )

                logging.warning(
                    f"OPENAI_KEY_PRESENT = {len(AZURE_OPENAI_API_KEY or '') > 0}"
                )

                response = (
                    self.client
                    .chat
                    .completions
                    .create(

                        model=
                            AZURE_OPENAI_DEPLOYMENT_NAME,

                        messages=
                            messages,

                        max_completion_tokens=
                            GPT_MAX_RESPONSE_TOKENS,

                        timeout=
                            OPENAI_TIMEOUT_SECONDS
                    )
                )

                text = (
                    response
                    .choices[0]
                    .message.content
                    .strip()
                )

                if (
                    len(text)
                    <
                    MIN_DESCRIPTION_LENGTH
                ):

                    raise RuntimeError(
                        "Response too short."
                    )

                return text

            except Exception as ex:

                error_text = (
                    str(ex)
                ).lower()

                logging.exception(
                    f"GPT request failed: {ex}"
                )

                # ----------------------------------
                # CONTENT FILTER FALLBACK
                # ----------------------------------

                if (
                    "content_filter"
                    in error_text
                    and
                    OPENAI_CONTENT_FILTER_RETRY
                    and
                    transcript_context
                ):

                    logging.warning(
                        "Retrying without transcript."
                    )

                    return self.analyze_frame(

                        transcript_context="",

                        previous_context=
                            previous_context,

                        image_sequence=
                            image_sequence,

                        attempt_without_transcript=True
                    )

                # ----------------------------------
                # RETRY
                # ----------------------------------

                if (
                    attempt
                    <
                    MAX_OPENAI_RETRIES
                    -
                    1
                ):

                    time.sleep(
                        retry_delay
                    )

                    retry_delay *= (
                        OPENAI_RETRY_MULTIPLIER
                    )

                    continue

                raise