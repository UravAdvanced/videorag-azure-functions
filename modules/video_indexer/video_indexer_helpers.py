def safe_get_duration_seconds(
    insights_json: dict
) -> float:

    try:

        videos = (
            insights_json.get(
                "videos",
                []
            )
        )

        if not videos:
            return 0.0

        duration = (
            videos[0]
            .get(
                "insights",
                {}
            )
            .get(
                "duration",
                0
            )
        )

        return float(duration)

    except Exception:

        return 0.0