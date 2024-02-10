import importlib
import logging

logger = logging.getLogger(__name__)


# Automatically register error and output types from
# commonly used libraries.
integrations = ("httpx", "requests")
for name in integrations:
    try:
        importlib.import_module(f"dispatch.integrations.{name}")
    except (ImportError, AttributeError):
        pass
    else:
        logger.debug("registered %s integration", name)
