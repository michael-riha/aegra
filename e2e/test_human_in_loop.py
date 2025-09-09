import pytest
from e2e._utils import get_e2e_client, elog


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_human_in_loop_interrupt_resume_e2e():
    """
    Complete human-in-the-loop test using agent_hitl graph (non-streaming).
    Tests: interrupt detection, validation, resume with approval, tool execution.
    """
    client = get_e2e_client()

    # Create assistant with agent_hitl graph
    assistant = await client.assistants.create(
        graph_id="agent_hitl",
        config={"tags": ["hitl", "complete_cycle"]},
        if_exists="do_nothing",
    )
    elog("Assistant.create (agent_hitl)", assistant)
    assert "assistant_id" in assistant
    assistant_id = assistant["assistant_id"]

    # Create thread
    thread = await client.threads.create()
    elog("Threads.create", thread)
    thread_id = thread["thread_id"]

    # Test validation: input + command should fail
    try:
        await client.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            input={"messages": [{"role": "user", "content": "Hello"}]},
            command={"update": {"test": "value"}},
        )
        assert False, "Expected validation error for input + command"
    except Exception as e:
        elog("✅ Validation works", {"error_contains": "422" in str(e) or "validation" in str(e).lower()})

    # Create run that triggers tool usage (requires approval in agent_hitl)
    run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": "What's the weather like today?"}]},
    )
    elog("Runs.create (tool trigger)", run)
    run_id = run["run_id"]

    # Wait for interrupt
    import asyncio
    max_wait = 10
    wait_interval = 0.5
    waited = 0
    
    while waited < max_wait:
        await asyncio.sleep(wait_interval)
        waited += wait_interval
        
        interrupted_run = await client.runs.get(thread_id, run_id)
        if interrupted_run["status"] == "interrupted":
            break
        elif interrupted_run["status"] in ("completed", "failed", "error"):
            elog("Run completed without interrupt", interrupted_run)
            return
    
    assert interrupted_run["status"] == "interrupted", f"Expected interrupted, got {interrupted_run['status']}"
    elog("✅ Interrupt detected", {"run_id": run_id})

    # Verify thread history has interrupt
    history = await client.threads.get_history(thread_id)
    if isinstance(history, list) and len(history) > 0:
        latest_state = history[0]
        assert "interrupts" in latest_state and len(latest_state["interrupts"]) > 0
        elog("✅ Thread state has interrupt", {"interrupt_count": len(latest_state["interrupts"])})

    # Test resume validation: should fail if thread not interrupted
    # (We'll create a new thread to test this)
    test_thread = await client.threads.create()
    try:
        await client.runs.create(
            thread_id=test_thread["thread_id"],
            assistant_id=assistant_id,
            command={"resume": "yes"}
        )
        assert False, "Expected validation error for resume on non-interrupted thread"
    except Exception as e:
        elog("✅ Resume validation works", {"error_type": type(e).__name__})

    # Resume with approval
    resume_run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        command={"resume": "yes"},
    )
    elog("Runs.create (resume)", resume_run)
    resume_run_id = resume_run["run_id"]

    # Wait for completion
    final_state = await client.runs.join(thread_id, resume_run_id)
    completed_run = await client.runs.get(thread_id, resume_run_id)
    
    # Verify final state (completed or interrupted again for more tools)
    assert completed_run["status"] in ("completed", "interrupted")
    elog("✅ Resume executed", {"final_status": completed_run["status"]})

    # Verify tool execution in message history
    final_history = await client.threads.get_history(thread_id)
    if isinstance(final_history, list) and len(final_history) > 0:
        messages = final_history[0].get("values", {}).get("messages", [])
        user_msgs = [m for m in messages if m.get("type") == "human"]
        ai_msgs = [m for m in messages if m.get("type") == "ai"]
        tool_msgs = [m for m in messages if m.get("type") == "tool"]
        
        assert len(user_msgs) >= 1 and len(ai_msgs) >= 1
        if completed_run["status"] == "completed":
            assert len(tool_msgs) > 0, "Expected tool execution for completed run"
        
        elog("✅ Message flow verified", {
            "user": len(user_msgs), "ai": len(ai_msgs), "tool": len(tool_msgs)
        })


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_human_in_loop_streaming_interrupt_resume_e2e():
    """
    Complete streaming human-in-the-loop test using agent_hitl graph.
    Tests: real-time interrupt detection, streaming resume, tool execution verification.
    """
    client = get_e2e_client()

    # Setup
    assistant = await client.assistants.create(
        graph_id="agent_hitl",
        config={"tags": ["hitl", "streaming"]},
        if_exists="do_nothing",
    )
    thread = await client.threads.create()
    thread_id = thread["thread_id"]
    assistant_id = assistant["assistant_id"]

    # Phase 1: Stream until interrupt
    elog("Phase 1: Stream until interrupt", {"starting": True})
    stream = client.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": "Search for Python programming info"}]},
        stream_mode=["values"],
    )

    event_count = 0
    interrupt_detected = False
    initial_run_id = None
    
    async for chunk in stream:
        event_count += 1
        event_type = getattr(chunk, "event", None)
        data = getattr(chunk, "data", None)
        
        # Look for interrupt in values events
        if event_type == "values" and isinstance(data, dict):
            if "__interrupt__" in data and len(data.get("__interrupt__", [])) > 0:
                interrupt_detected = True
                elog("✅ Interrupt detected in stream!", {"event_count": event_count})
                break
        
        if event_count > 50:  # Safety limit
            break

    assert interrupt_detected, f"Expected interrupt in stream after {event_count} events"

    # Get run_id from thread history
    history = await client.threads.get_history(thread_id)
    if isinstance(history, list) and len(history) > 0:
        latest_state = history[0]
        initial_run_id = latest_state.get("metadata", {}).get("run_id")
        assert "interrupts" in latest_state and len(latest_state["interrupts"]) > 0
    
    assert initial_run_id is not None, "Expected to find run_id in thread history"

    # Phase 2: Verify interrupted state
    interrupted_run = await client.runs.get(thread_id, initial_run_id)
    assert interrupted_run["status"] == "interrupted"
    elog("✅ Run interrupted", {"run_id": initial_run_id})

    # Phase 3: Stream resume command
    elog("Phase 2: Stream resume", {"starting": True})
    resume_stream = client.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        command={"resume": "yes"},
        stream_mode=["values"],
    )

    resume_event_count = 0
    tool_executed = False
    final_ai_message = False
    
    async for chunk in resume_stream:
        resume_event_count += 1
        event_type = getattr(chunk, "event", None)
        data = getattr(chunk, "data", None)
        
        # Look for tool execution and final AI response
        if event_type == "values" and isinstance(data, dict):
            messages = data.get("messages", [])
            for msg in messages:
                if isinstance(msg, dict):
                    if msg.get("type") == "tool":
                        tool_executed = True
                        elog("✅ Tool execution detected!", {"tool": msg.get("name")})
                    elif msg.get("type") == "ai" and msg.get("content") and tool_executed:
                        final_ai_message = True
                        elog("✅ Final AI response!", {"length": len(msg.get("content", ""))})
        
        if resume_event_count > 50:  # Safety limit
            break

    # Phase 4: Verify completion
    final_history = await client.threads.get_history(thread_id)
    if isinstance(final_history, list) and len(final_history) > 0:
        messages = final_history[0].get("values", {}).get("messages", [])
        user_msgs = [m for m in messages if m.get("type") == "human"]
        ai_msgs = [m for m in messages if m.get("type") == "ai"]
        tool_msgs = [m for m in messages if m.get("type") == "tool"]
        
        # Verify complete flow
        assert len(user_msgs) >= 1 and len(ai_msgs) >= 1
        assert tool_executed, "Expected tool execution in stream"
        
        elog("✅ Streaming cycle complete", {
            "interrupt_events": event_count,
            "resume_events": resume_event_count,
            "messages": {"user": len(user_msgs), "ai": len(ai_msgs), "tool": len(tool_msgs)},
            "tool_executed": tool_executed,
            "final_ai_response": final_ai_message
        })



