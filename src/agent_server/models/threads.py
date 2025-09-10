"""Thread-related Pydantic models for Agent Protocol"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class ThreadCreate(BaseModel):
    """Request model for creating threads"""
    metadata: Optional[Dict[str, Any]] = Field(None, description="Thread metadata")
    initial_state: Optional[Dict[str, Any]] = Field(None, description="LangGraph initial state")


class Thread(BaseModel):
    """Thread entity model"""
    thread_id: str
    status: str = "idle"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ThreadList(BaseModel):
    """Response model for listing threads"""
    threads: List[Thread]
    total: int


class ThreadSearchRequest(BaseModel):
    """Request model for thread search"""
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    status: Optional[str] = Field(None, description="Thread status filter")
    limit: Optional[int] = Field(20, le=100, ge=1, description="Maximum results")
    offset: Optional[int] = Field(0, ge=0, description="Results offset")
    order_by: Optional[str] = Field("created_at DESC", description="Sort order")


class ThreadSearchResponse(BaseModel):
    """Response model for thread search"""
    threads: List[Thread]
    total: int
    limit: int
    offset: int


class ThreadCheckpoint(BaseModel):
    """Checkpoint identifier for thread history"""
    checkpoint_id: Optional[str] = None
    thread_id: Optional[str] = None
    checkpoint_ns: Optional[str] = ""


class ThreadState(BaseModel):
    """Thread state model for history endpoint"""
    values: Dict[str, Any] = Field(description="Channel values (messages, etc.)")
    next: List[str] = Field(default_factory=list, description="Next nodes to execute")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Tasks to execute")
    interrupts: List[Dict[str, Any]] = Field(default_factory=list, description="Interrupt data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Checkpoint metadata")
    created_at: Optional[datetime] = Field(None, description="Timestamp of state creation")
    checkpoint: ThreadCheckpoint = Field(description="Current checkpoint")
    parent_checkpoint: Optional[ThreadCheckpoint] = Field(None, description="Parent checkpoint")
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID (for backward compatibility)")
    parent_checkpoint_id: Optional[str] = Field(None, description="Parent checkpoint ID (for backward compatibility)")


class ThreadHistoryRequest(BaseModel):
    """Request model for thread history endpoint"""
    limit: Optional[int] = Field(10, ge=1, le=1000, description="Number of states to return")
    before: Optional[str] = Field(None, description="Return states before this checkpoint ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Filter by metadata")
    checkpoint: Optional[Dict[str, Any]] = Field(None, description="Checkpoint for subgraph filtering")
    subgraphs: Optional[bool] = Field(False, description="Include states from subgraphs")
    checkpoint_ns: Optional[str] = Field(None, description="Checkpoint namespace")
