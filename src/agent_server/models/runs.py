"""Run-related Pydantic models for Agent Protocol"""
from typing import Optional, Dict, Any, List, Union, Sequence
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class RunCreate(BaseModel):
    """Request model for creating runs"""
    assistant_id: str = Field(..., description="Assistant to execute")
    input: Optional[Dict[str, Any]] = Field(
        None,
        description="Input data for the run. Optional when resuming from a checkpoint.",
    )
    config: Optional[Dict[str, Any]] = Field({}, description="LangGraph execution config")
    context: Optional[Dict[str, Any]] = Field({}, description="LangGraph execution context")
    checkpoint: Optional[Dict[str, Any]] = Field(
        None,
        description="Checkpoint configuration (e.g., {'checkpoint_id': '...', 'checkpoint_ns': ''})",
    )
    stream: bool = Field(False, description="Enable streaming response")
    stream_mode: Optional[str | list[str]] = Field(None, description="Requested stream mode(s) as per LangGraph")
    on_disconnect: Optional[str] = Field(
        None,
        description="Behavior on client disconnect: 'cancel' or 'continue' (default).",
    )
    
    multitask_strategy: Optional[str] = Field(
        None,
        description="Strategy for handling concurrent runs on same thread: 'reject', 'interrupt', 'rollback', or 'enqueue'.",
    )
    
    # Human-in-the-loop fields (core HITL functionality)
    command: Optional[Dict[str, Any]] = Field(
        None,
        description="Command for resuming interrupted runs with state updates or navigation",
    )
    interrupt_before: Optional[Union[str, List[str]]] = Field(
        None,
        description="Nodes to interrupt immediately before they get executed. Use '*' for all nodes.",
    )
    interrupt_after: Optional[Union[str, List[str]]] = Field(
        None,
        description="Nodes to interrupt immediately after they get executed. Use '*' for all nodes.",
    )
    
    @model_validator(mode='after')
    def validate_input_command_exclusivity(self):
        """Ensure input and command are mutually exclusive"""
        # Allow empty input dict when command is present (frontend compatibility)
        if self.input is not None and self.command is not None:
            # If input is just an empty dict, treat it as None for compatibility
            if self.input == {}:
                self.input = None
            else:
                raise ValueError("Cannot specify both 'input' and 'command' - they are mutually exclusive")
        if self.input is None and self.command is None:
            raise ValueError("Must specify either 'input' or 'command'")
        return self


class Run(BaseModel):
    """Run entity model"""
    run_id: str
    thread_id: str
    assistant_id: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    context: Optional[Dict[str, Any]] = {}
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RunList(BaseModel):
    """Response model for listing runs"""
    runs: List[Run]
    total: int


class RunStatus(BaseModel):
    """Simple run status response"""
    run_id: str
    status: str
    message: Optional[str] = None
