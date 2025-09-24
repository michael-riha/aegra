# https://python.langchain.com/docs/how_to/custom_callbacks/
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from mcp_agent.utils.logger import setup_logger

# Set up logger for this class
logger = setup_logger(__name__)


class MyCustomHandler(BaseCallbackHandler):
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        logger.debug("Token received: %s", token)  # Changed from print

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs
    ) -> None:
        logger.info("LLM started with prompts: %s", prompts)  # Changed from print

    def on_llm_end(self, response: dict[str, Any], **kwargs) -> None:
        logger.info("LLM ended with response: %s", response)  # Changed from print

    def on_chain_start(
        self, serialized: dict[str, Any], inputs: dict[str, Any], **kwargs
    ) -> None:
        logger.info("Chain started with inputs: %s", inputs)  # Changed from print

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs
    ) -> None:
        logger.info("Tool started with input: %s", input_str)  # Changed from print

    def on_agent_action(self, action: dict[str, Any], **kwargs) -> None:
        logger.info("Agent action: %s", action)  # Changed from print

    def on_agent_finish(self, finish: dict[str, Any], **kwargs) -> None:
        logger.info("Agent finished: %s", finish)  # Changed from print
