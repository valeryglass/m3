from app.schemas.episode import Episode


def test_episode_schema_accepts_valid_episode():
    episode = Episode.model_validate(
        {
            "id": "episode-20260430-1",
            "date": "2026-04-30",
            "source": "telegram-chat:123",
            "observed": {
                "situation": {
                    "value": "Asked a question.",
                    "source_quote": "I asked a question",
                },
                "automatic_thought": {
                    "value": "They will judge me.",
                    "source_quote": "they will judge me",
                },
                "emotion": {"value": "Anxiety.", "source_quote": "anxious"},
                "body": {"value": "Tight chest.", "source_quote": "tight chest"},
                "behavior": {
                    "value": "Closed the chat.",
                    "source_quote": "closed the chat",
                },
                "short_term_consequence": {
                    "value": "Relief.",
                    "source_quote": "relieved",
                },
                "long_term_consequence": {
                    "value": "Question stayed unresolved.",
                    "source_quote": "still did not know",
                },
            },
            "derived": {
                "atomic_thoughts": [
                    {
                        "id": "atomic-thought-1",
                        "text": "They will judge me.",
                        "source_field": "observed.automatic_thought",
                        "source_quote": "they will judge me",
                        "confidence": "medium",
                    }
                ],
                "cognitive_distortions": [],
            },
        }
    )

    assert episode.id == "episode-20260430-1"
