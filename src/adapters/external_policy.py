"""Provider boundary policy. Unset preserves the production contract."""
import logging
import os

from models.errors import ConfigError

logger = logging.getLogger(__name__)


def require_external_api(provider: str, operation: str) -> None:
    if os.getenv("RISKLIVE_EXTERNAL_APIS_ENABLED", "true").lower() != "true":
        raise ConfigError(f"External APIs disabled: {provider}/{operation}")


def audit_request(provider: str, operation: str) -> None:
    if os.getenv("RISKLIVE_ENVIRONMENT") == "development":
        from utils.logging import configure_logging
        configure_logging()
    # Plain message fields survive existing structured logging allowlists.
    logger.info("provider_request provider=%s operation=%s request_count=1 input_tokens=%s output_tokens=%s",
                provider, operation, None, None)
