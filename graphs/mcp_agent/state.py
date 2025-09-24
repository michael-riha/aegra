from typing import Any, TypedDict
from langchain_core.tools import Tool
from langgraph.prebuilt import ToolNode

# State class with proper typing
class AgentState(TypedDict):
    messages: list
    initial_prompt: list


# class Context(TypedDict):
#     llm: Any  # Using Any for flexibility
#     toolNode: ToolNode
#     tools: list[Tool]
