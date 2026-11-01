import anthropic

from app.config import ANTHROPIC_API_KEY, has_anthropic_key


class AIUnavailableError(RuntimeError):
    """Raised when an AI feature is used without ANTHROPIC_API_KEY configured."""


_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if not has_anthropic_key():
        raise AIUnavailableError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file to enable "
            "AI campaign generation and AI optimization insights."
        )
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client
