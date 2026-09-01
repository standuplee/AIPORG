"""Logging setup for AIPORG 2.0."""

import logging


_HANDLER_MARKER = "_aiporg2_handler"


def configure_logging(level: str = "INFO") -> None:
    """Install one plain stderr handler and make repeated calls harmless."""

    normalized_level = level.upper()
    numeric_level = getattr(logging, normalized_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unsupported log level: {level}")

    root = logging.getLogger()
    root.setLevel(numeric_level)
    handlers = [handler for handler in root.handlers if getattr(handler, _HANDLER_MARKER, False)]
    if handlers:
        for handler in handlers:
            handler.setLevel(numeric_level)
        return

    handler = logging.StreamHandler()
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(numeric_level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(handler)
