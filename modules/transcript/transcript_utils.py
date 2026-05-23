import logging


def parse_vi_time_string(time_str: str) -> float:
    """
    Converts Video Indexer timestamps like:

    00:01:23.456

    into:

    83.456 seconds
    """

    if not time_str:
        return 0.0

    try:
        parts = time_str.split(":")

        hours = int(parts[0])
        minutes = int(parts[1])

        sec_parts = parts[2].split(".")

        seconds = int(sec_parts[0])

        milliseconds = (
            int(sec_parts[1])
            if len(sec_parts) > 1
            else 0
        )

        return (
            hours * 3600
            + minutes * 60
            + seconds
            + milliseconds / 1000.0
        )

    except Exception as e:
        logging.exception(
            f"Unable to parse Video Indexer timestamp: {time_str}"
        )
        return 0.0


def get_transcript_for_timestamp(
    transcript_entries: list,
    target_seconds: float,
    context_window_seconds: int
) -> str:
    """
    Returns transcript surrounding a frame timestamp.
    """

    if not transcript_entries:
        return "No transcript available."

    min_time = target_seconds - context_window_seconds
    max_time = target_seconds + context_window_seconds

    relevant_text = []

    for entry in transcript_entries:

        try:

            instance = entry["instances"][0]

            start_seconds = parse_vi_time_string(
                instance["start"]
            )

            end_seconds = parse_vi_time_string(
                instance["end"]
            )

            overlap = (
                max(start_seconds, min_time)
                <
                min(end_seconds, max_time)
            )

            if overlap:
                relevant_text.append(
                    entry.get("text", "")
                )

        except Exception:
            continue

    if not relevant_text:
        return "No speech found."

    return " ".join(relevant_text)