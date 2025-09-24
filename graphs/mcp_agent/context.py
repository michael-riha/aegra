"""Define the configurable parameters for the agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Annotated, Any
from langchain_core.tools import Tool
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import ToolNode
from . import prompts


@dataclass(kw_only=True)
class Context:
    """The context for the agent."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )
    # Using Any for flexibility
    llm: BaseChatModel  = field(
        default=None,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )

    toolNode: ToolNode = field(
        default=None,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )
    
    tools: list[Tool] = field(
        default=None,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )
    

    def __post_init__(self) -> None:
        """Fetch env vars for attributes that were not passed as args."""
        for f in fields(self):
            if not f.init:
                continue

            if getattr(self, f.name) == f.default:
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
