"""Strict readiness policy for JASSIM's private local inference route."""


def local_model_ready(model_state):
    """Return true only when Ollama is reachable and the configured model exists."""
    if not isinstance(model_state, dict):
        return False
    return bool(model_state.get("reachable") and model_state.get("model_ready"))
