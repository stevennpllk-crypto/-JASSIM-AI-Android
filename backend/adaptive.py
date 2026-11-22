"""Private-only inference policy for JASSIM AI.

No public model providers are configured, evaluated, or called by this module.
All text inference must go through the owner's local Ollama instance.
"""


def provider_stats():
    """Public-provider statistics are intentionally unavailable in private-only mode."""
    return []


def evaluate_providers():
    """Keep the legacy admin endpoint safe without making any outbound requests."""
    return {
        "enabled": False,
        "tested": 0,
        "results": [],
        "message": "External AI providers are disabled; JASSIM uses its private local model only.",
    }


def answer_with_provider(messages, allow_external=False):
    """Reject every external inference request, including admin/NPC exceptions."""
    raise RuntimeError("external_chat_disabled")


def external_chat_enabled():
    return False


def npc_chat_enabled():
    return False
