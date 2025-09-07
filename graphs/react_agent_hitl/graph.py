"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from react_agent_hitl.context import Context
from react_agent_hitl.state import InputState, State
from react_agent_hitl.tools import TOOLS
from react_agent_hitl.utils import load_chat_model

# Define the function that calls the model


async def call_model(
    state: State, runtime: Runtime[Context]
) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}


async def human_approval(
    state: State, runtime: Runtime[Context]
) -> Dict:
    """Request human approval before executing tools.
    
    This node demonstrates the human-in-the-loop interrupt functionality.
    It pauses execution and waits for human input before proceeding.
    
    This node does NOT modify the messages - it only handles the interrupt.
    """
    # Find the last message with tool calls
    tool_message = None
    for msg in reversed(state.messages):
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            tool_message = msg
            break
    
    if not tool_message:
        print("No tool calls found to approve.")
        return {}  # No state changes
    
    print("---Human Approval Required---")
    print(f"The agent wants to execute {len(tool_message.tool_calls)} tool(s)")
    
    # Show tool details
    for tool_call in tool_message.tool_calls:
        print(f"  - {tool_call['name']}: {tool_call.get('args', {})}")
    
    # This will pause execution and wait for human input
    # The approval/denial is handled by the interrupt system, not by modifying messages
    approval = interrupt({
        "message": "Do you approve tool execution?", 
        "tools": [{"name": tc["name"], "args": tc.get("args", {})} for tc in tool_message.tool_calls]
    })
    
    approval_str = str(approval).lower().strip() if approval else "no"
    print(f"Human approval: {approval_str}")
    
    approved = approval_str.startswith('y')
    
    if not approved:
        # Human denied - we need to create tool responses to satisfy OpenAI's requirements
        # Otherwise OpenAI will throw error about missing tool responses
        tool_responses = []
        for tool_call in tool_message.tool_calls:
            tool_responses.append(ToolMessage(
                content="Tool execution cancelled by human operator.",
                tool_call_id=tool_call["id"],
                name=tool_call["name"]
            ))
        return {"human_approved": False, "messages": tool_responses}
    
    # Store the approval decision in a custom state field (not messages)
    return {"human_approved": True}


# Define a new graph

builder = StateGraph(State, input_schema=InputState, context_schema=Context)

# Define the nodes we will cycle between
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node(human_approval)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["__end__", "human_approval"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.
    If it does, we route to human approval first.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "human_approval").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # If there is no tool call, then we finish
    if not last_message.tool_calls:
        return "__end__"
    # Otherwise we need human approval first
    return "human_approval"


def route_after_approval(state: State) -> Literal["__end__", "tools"]:
    """Route after human approval.
    
    Check if human approved or denied the tool execution using the state field.
    """
    # Check the human_approved state field set by the human_approval node
    if state.human_approved:
        # Human approved - check if we have tool calls to execute
        for msg in reversed(state.messages):
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                return "tools"
    
    # Human denied or no tool calls found
    return "__end__"


# Add conditional edges
builder.add_conditional_edges(
    "call_model",
    route_model_output,
    path_map=["human_approval", END]
)

builder.add_conditional_edges(
    "human_approval",
    route_after_approval,
    path_map=["tools", END]
)

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")

# Compile the builder into an executable graph
graph = builder.compile(name="ReAct Agent")