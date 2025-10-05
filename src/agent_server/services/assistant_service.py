"""Service layer for assistant business logic

This service encapsulates all business logic for assistant management, following
a layered architecture pattern. The code was extracted from api/assistants.py
to separate concerns and improve maintainability.

Responsibilities:
- Business logic and validation
- Database operations via SQLAlchemy ORM
- Graph schema extraction and manipulation
- Coordination between different components

This is the first service layer implementation in Aegra. The pattern will be
applied to other APIs (runs, threads, crons) as part of ongoing refactoring.
"""
from uuid import uuid4
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional
import uuid
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException

from ..models import Assistant, AssistantCreate, AssistantUpdate
from ..core.orm import Assistant as AssistantORM, AssistantVersion as AssistantVersionORM, get_session
from ..services.langgraph_service import LangGraphService, get_langgraph_service


def to_pydantic(row: AssistantORM) -> Assistant:
    """Convert SQLAlchemy ORM object to Pydantic model with proper type casting."""
    row_dict = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    # Cast UUIDs to str so they match the Pydantic schema
    if "assistant_id" in row_dict and row_dict["assistant_id"] is not None:
        row_dict["assistant_id"] = str(row_dict["assistant_id"])
    if "user_id" in row_dict and isinstance(row_dict["user_id"], uuid.UUID):
        row_dict["user_id"] = str(row_dict["user_id"])
    return Assistant.model_validate(row_dict)


def _state_jsonschema(graph) -> dict | None:
    """Extract state schema from graph channels"""
    from typing import Any
    from langgraph._internal._pydantic import create_model
    
    fields: dict = {}
    for k in graph.stream_channels_list:
        v = graph.channels[k]
        try:
            create_model(k, __root__=(v.UpdateType, None)).model_json_schema()
            fields[k] = (v.UpdateType, None)
        except Exception:
            fields[k] = (Any, None)
    return create_model(graph.get_name("State"), **fields).model_json_schema()


def _get_configurable_jsonschema(graph) -> dict:
    """Get the JSON schema for the configurable part of the graph"""
    from pydantic import TypeAdapter
    
    EXCLUDED_CONFIG_SCHEMA = {"__pregel_resuming", "__pregel_checkpoint_id"}
    
    config_schema = graph.config_schema()
    model_fields = getattr(config_schema, "model_fields", None) or getattr(
        config_schema, "__fields__", None
    )
    
    if model_fields is not None and "configurable" in model_fields:
        configurable = TypeAdapter(model_fields["configurable"].annotation)
        json_schema = configurable.json_schema()
        if json_schema:
            for key in EXCLUDED_CONFIG_SCHEMA:
                json_schema["properties"].pop(key, None)
        if (
            hasattr(graph, "config_type")
            and graph.config_type is not None
            and hasattr(graph.config_type, "__name__")
        ):
            json_schema["title"] = graph.config_type.__name__
        return json_schema
    return {}


def _extract_graph_schemas(graph) -> dict:
    """Extract schemas from a compiled LangGraph graph object"""
    try:
        input_schema = graph.get_input_jsonschema()
    except Exception:
        input_schema = None
    
    try:
        output_schema = graph.get_output_jsonschema()
    except Exception:
        output_schema = None
    
    try:
        state_schema = _state_jsonschema(graph)
    except Exception:
        state_schema = None
    
    try:
        config_schema = _get_configurable_jsonschema(graph)
    except Exception:
        config_schema = None
    
    try:
        context_schema = graph.get_context_jsonschema()
    except Exception:
        context_schema = None
    
    return {
        "input_schema": input_schema,
        "output_schema": output_schema,
        "state_schema": state_schema,
        "config_schema": config_schema,
        "context_schema": context_schema,
    }


class AssistantService:
    """Service for managing assistants"""
    
    def __init__(self, session: AsyncSession, langgraph_service: LangGraphService):
        self.session = session
        self.langgraph_service = langgraph_service
    
    async def create_assistant(
        self,
        request: AssistantCreate,
        user_identity: str
    ) -> Assistant:
        """Create a new assistant"""
        # Get LangGraph service to validate graph
        available_graphs = self.langgraph_service.list_graphs()
        
        # Use graph_id as the main identifier
        graph_id = request.graph_id
        
        if graph_id not in available_graphs:
            raise HTTPException(
                400,
                f"Graph '{graph_id}' not found in aegra.json. Available: {list(available_graphs.keys())}"
            )
        
        # Validate graph can be loaded
        try:
            graph = await self.langgraph_service.get_graph(graph_id)
        except Exception as e:
            raise HTTPException(400, f"Failed to load graph: {str(e)}")

        config = request.config
        context = request.context

        if config.get("configurable") and context:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both configurable and context. Prefer setting context alone. Context was introduced in LangGraph 0.6.0 and is the long term planned replacement for configurable.",
            )

        # Keep config and context up to date with one another
        if config.get("configurable"):
            context = config["configurable"]
        elif context:
            config["configurable"] = context
        
        # Generate assistant_id if not provided
        assistant_id = request.assistant_id or str(uuid4())
        
        # Generate name if not provided
        name = request.name or f"Assistant for {graph_id}"
        
        # Check if an assistant already exists for this user, graph and config pair
        existing_stmt = select(AssistantORM).where(
            AssistantORM.user_id == user_identity,
            or_(
                (AssistantORM.graph_id == graph_id) & (AssistantORM.config == config),
                AssistantORM.assistant_id == assistant_id
            )
        )
        existing = await self.session.scalar(existing_stmt)
        
        if existing:
            if request.if_exists == "do_nothing":
                return to_pydantic(existing)
            else:  # error (default)
                raise HTTPException(409, f"Assistant '{assistant_id}' already exists")
        
        # Create assistant record
        assistant_orm = AssistantORM(
            assistant_id=assistant_id,
            name=name,
            description=request.description,
            config=config,
            context=context,
            graph_id=graph_id,
            user_id=user_identity,
            metadata_dict=request.metadata,
            version=1
        )
        
        self.session.add(assistant_orm)
        await self.session.commit()
        await self.session.refresh(assistant_orm)

        # Create initial version record
        assistant_version_orm = AssistantVersionORM(
            assistant_id=assistant_id,
            version=1,
            graph_id=graph_id,
            config=config,
            context=context,
            created_at=datetime.now(UTC),
            name=name,
            description=request.description,
            metadata_dict=request.metadata
        )
        self.session.add(assistant_version_orm)
        await self.session.commit()
        
        return to_pydantic(assistant_orm)
    
    async def list_assistants(
        self,
        user_identity: str
    ) -> List[Assistant]:
        """List user's assistants"""
        # Filter assistants by user
        stmt = select(AssistantORM).where(AssistantORM.user_id == user_identity)
        result = await self.session.scalars(stmt)
        user_assistants = [to_pydantic(a) for a in result.all()]
        return user_assistants
    
    async def search_assistants(
        self,
        request: Any,  # AssistantSearchRequest
        user_identity: str
    ) -> List[Assistant]:
        """Search assistants with filters"""
        # Start with user's assistants
        stmt = select(AssistantORM).where(AssistantORM.user_id == user_identity)
        
        # Apply filters
        if request.name:
            stmt = stmt.where(AssistantORM.name.ilike(f"%{request.name}%"))
        
        if request.description:
            stmt = stmt.where(AssistantORM.description.ilike(f"%{request.description}%"))
        
        if request.graph_id:
            stmt = stmt.where(AssistantORM.graph_id == request.graph_id)

        if request.metadata:
            stmt = stmt.where(AssistantORM.metadata_dict.op("@>")(request.metadata))
        
        # Apply pagination
        offset = request.offset or 0
        limit = request.limit or 20
        stmt = stmt.offset(offset).limit(limit)
        
        result = await self.session.scalars(stmt)
        paginated_assistants = [to_pydantic(a) for a in result.all()]
        
        return paginated_assistants
    
    async def count_assistants(
        self,
        request: Any,  # AssistantSearchRequest
        user_identity: str
    ) -> int:
        """Count assistants with filters"""
        stmt = select(func.count()).where(AssistantORM.user_id == user_identity)

        if request.name:
            stmt = stmt.where(AssistantORM.name.ilike(f"%{request.name}%"))

        if request.description:
            stmt = stmt.where(AssistantORM.description.ilike(f"%{request.description}%"))

        if request.graph_id:
            stmt = stmt.where(AssistantORM.graph_id == request.graph_id)

        if request.metadata:
            stmt = stmt.where(AssistantORM.metadata_dict.op("@>")(request.metadata))

        total = await self.session.scalar(stmt)
        return total or 0
    
    async def get_assistant(
        self,
        assistant_id: str,
        user_identity: str
    ) -> Assistant:
        """Get assistant by ID"""
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(
                AssistantORM.user_id == user_identity,
                AssistantORM.user_id == "system"
            )
        )
        assistant = await self.session.scalar(stmt)
        
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")
        
        return to_pydantic(assistant)
    
    async def update_assistant(
        self,
        assistant_id: str,
        request: AssistantUpdate,
        user_identity: str
    ) -> Assistant:
        """Update assistant by ID"""
        metadata = request.metadata or {}
        config = request.config or {}
        context = request.context or {}

        if config.get("configurable") and context:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both configurable and context. Use only one.",
            )

        # Keep config and context up to date with one another
        if config.get("configurable"):
            context = config["configurable"]
        elif context:
            config["configurable"] = context

        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity
        )
        assistant = await self.session.scalar(stmt)
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        now = datetime.now(UTC)
        version_stmt = select(func.max(AssistantVersionORM.version)).where(
            AssistantVersionORM.assistant_id == assistant_id
        )
        max_version = await self.session.scalar(version_stmt)
        new_version = (max_version or 1) + 1  if max_version is not None else 1

        new_version_details = {
            "assistant_id": assistant_id,
            "version": new_version,
            "graph_id": request.graph_id or assistant.graph_id,
            "config": config,
            "context": context,
            "created_at": now,
            "name": request.name or assistant.name,
            "description": request.description or assistant.description,
            "metadata_dict": metadata
        }

        assistant_version_orm = AssistantVersionORM(**new_version_details)
        self.session.add(assistant_version_orm)
        await self.session.commit()

        assistant_update = update(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity
        ).values(
            name=new_version_details["name"],
            description=new_version_details["description"],
            graph_id=new_version_details["graph_id"],
            config=new_version_details["config"],
            context=new_version_details["context"],
            version=new_version,
            updated_at=now,
        )
        await self.session.execute(assistant_update)
        await self.session.commit()
        updated_assistant = await self.session.scalar(stmt)
        return to_pydantic(updated_assistant)
    
    async def delete_assistant(
        self,
        assistant_id: str,
        user_identity: str
    ) -> dict:
        """Delete assistant by ID"""
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity
        )
        assistant = await self.session.scalar(stmt)
        
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")
        
        await self.session.delete(assistant)
        await self.session.commit()

        return {"status": "deleted"}
    
    async def set_assistant_latest(
        self,
        assistant_id: str,
        version: int,
        user_identity: str
    ) -> Assistant:
        """Set the given version as the latest version of an assistant"""
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity
        )
        assistant = await self.session.scalar(stmt)
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        version_stmt = select(AssistantVersionORM).where(
            AssistantVersionORM.assistant_id == assistant_id,
            AssistantVersionORM.version == version
        )
        assistant_version = await self.session.scalar(version_stmt)
        if not assistant_version:
            raise HTTPException(404, f"Version '{version}' for Assistant '{assistant_id}' not found")

        assistant_update = update(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity
        ).values(
            name=assistant_version.name,
            description=assistant_version.description,
            config=assistant_version.config,
            context=assistant_version.context,
            graph_id=assistant_version.graph_id,
            version=version,
            updated_at=datetime.now(UTC)
        )
        await self.session.execute(assistant_update)
        await self.session.commit()
        updated_assistant = await self.session.scalar(stmt)
        return to_pydantic(updated_assistant)
    
    async def list_assistant_versions(
        self,
        assistant_id: str,
        user_identity: str
    ) -> List[Assistant]:
        """List all versions of an assistant"""
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity
        )
        assistant = await self.session.scalar(stmt)
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        stmt = select(AssistantVersionORM).where(
            AssistantVersionORM.assistant_id == assistant_id
        ).order_by(AssistantVersionORM.version.desc())
        result = await self.session.scalars(stmt)
        versions = result.all()

        if not versions:
            raise HTTPException(404, f"No versions found for Assistant '{assistant_id}'")

        # Convert to Pydantic models
        version_list = [
            Assistant(
                assistant_id=assistant_id,
                name=v.name,
                description=v.description,
                config=v.config,
                context=v.context,
                graph_id=v.graph_id,
                user_id=user_identity,
                version=v.version,
                created_at=v.created_at,
                updated_at=v.created_at,
                metadata_dict=v.metadata_dict
            ) for v in versions
        ]

        return version_list
    
    async def get_assistant_schemas(
        self,
        assistant_id: str,
        user_identity: str
    ) -> dict:
        """Get input, output, state, config and context schemas for an assistant"""
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(
                AssistantORM.user_id == user_identity,
                AssistantORM.user_id == "system"
            )
        )
        assistant = await self.session.scalar(stmt)
        
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")
        
        try:
            graph = await self.langgraph_service.get_graph(assistant.graph_id)
            schemas = _extract_graph_schemas(graph)
            
            return {
                "graph_id": assistant.graph_id,
                **schemas
            }
            
        except Exception as e:
            raise HTTPException(400, f"Failed to extract schemas: {str(e)}")
    
    async def get_assistant_graph(
        self,
        assistant_id: str,
        xray: bool | int,
        user_identity: str
    ) -> dict:
        """Get the graph structure for visualization"""
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(
                AssistantORM.user_id == user_identity,
                AssistantORM.user_id == "system"
            )
        )
        assistant = await self.session.scalar(stmt)
        
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")
        
        try:
            graph = await self.langgraph_service.get_graph(assistant.graph_id)
            
            # Validate xray if it's an integer (not a boolean)
            if isinstance(xray, int) and not isinstance(xray, bool) and xray <= 0:
                raise HTTPException(422, detail="Invalid xray value")
            
            try:
                drawable_graph = await graph.aget_graph(xray=xray)
                json_graph = drawable_graph.to_json()
                
                for node in json_graph.get("nodes", []):
                    if (data := node.get("data")) and isinstance(data, dict):
                        data.pop("id", None)
                
                return json_graph
            except NotImplementedError:
                raise HTTPException(422, detail="The graph does not support visualization")
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Failed to get graph: {str(e)}")
    
    async def get_assistant_subgraphs(
        self,
        assistant_id: str,
        namespace: str | None,
        recurse: bool,
        user_identity: str
    ) -> dict:
        """Get subgraphs of an assistant"""
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(
                AssistantORM.user_id == user_identity,
                AssistantORM.user_id == "system"
            )
        )
        assistant = await self.session.scalar(stmt)
        
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")
        
        try:
            graph = await self.langgraph_service.get_graph(assistant.graph_id)
            
            try:
                subgraphs = {
                    ns: _extract_graph_schemas(subgraph)
                    async for ns, subgraph in graph.aget_subgraphs(
                        namespace=namespace,
                        recurse=recurse
                    )
                }
                return subgraphs
            except NotImplementedError:
                raise HTTPException(422, detail="The graph does not support subgraphs")
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Failed to get subgraphs: {str(e)}")


def get_assistant_service(
    session: AsyncSession = Depends(get_session),
    langgraph_service: LangGraphService = Depends(get_langgraph_service)
) -> AssistantService:
    """Dependency injection for AssistantService"""
    return AssistantService(session, langgraph_service)