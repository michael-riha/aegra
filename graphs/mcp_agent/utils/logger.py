import logging
import os

# Configure default logging format
DEFAULT_FORMAT = "🤞 %(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LEVEL = logging.INFO

def setup_logger(
    name: str, level: int | None = None, format_str: str | None = None
) -> logging.Logger:
    """
    Set up and return a logger with the given name and configuration.

    Args:
        name: The name of the logger
        level: The logging level (defaults to environment variable LOG_LEVEL or INFO)
        format_str: The log format string

    Returns:
        A configured logger instance
    """
    # Get log level from environment or use default
    if level is None:
        env_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    # Get formatter
    formatter = logging.Formatter(format_str or DEFAULT_FORMAT)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
