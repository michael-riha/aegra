import copy
from typing import Any


def _should_skip_event(raw_event: Any) -> bool:
    """Check if an event should be skipped based on langsmith:nostream tag"""
    try:
        # Check if the event has metadata with tags containing 'langsmith:nostream'
        if isinstance(raw_event, tuple) and len(raw_event) >= 2:
            # For tuple events, check the third element (metadata tuple)
            metadata_tuple = raw_event[len(raw_event) - 1]
            if isinstance(metadata_tuple, tuple) and len(metadata_tuple) >= 2:
                # Get the second item in the metadata tuple
                metadata = metadata_tuple[1]
                if isinstance(metadata, dict) and "tags" in metadata:
                    tags = metadata["tags"]
                    if isinstance(tags, list) and "langsmith:nostream" in tags:
                        return True
        return False
    except Exception:
        # If we can't parse the event structure, don't skip it
        return False


def _merge_jsonb(*objects: dict) -> dict:
    """Mimics PostgreSQL's JSONB merge behavior"""
    result = {}
    for obj in objects:
        if obj is not None:
            result.update(copy.deepcopy(obj))
    return result
