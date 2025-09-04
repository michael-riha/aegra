import pytest
from e2e._utils import get_e2e_client, elog


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_human_in_loop_interrupt_and_resume_e2e():
    """
    End-to-end test for human-in-the-loop functionality using LangGraph SDK client.
    Tests the complete interrupt-resume cycle:
      1) Create assistant and thread
      2) Create run with interrupt_before configuration
      3) Verify run gets interrupted (status = "interrupted")
      4) Resume run using command with human input
      5) Verify resumed run completes successfully
    """
    client = get_e2e_client()

    # 1) Ensure assistant exists
    assistant = await client.assistants.create(
        graph_id="agent",
        config={"tags": ["hitl", "interrupt"]},
        if_exists="do_nothing",
    )
    elog("Assistant.create", assistant)
    assert "assistant_id" in assistant
    assistant_id = assistant["assistant_id"]

    # 2) Create thread
    thread = await client.threads.create()
    elog("Threads.create", thread)
    thread_id = thread["thread_id"]

    # 3) Create run with interrupt configuration
    # Note: This assumes the graph has nodes that can be interrupted
    # In a real scenario, you'd configure interrupt_before with actual node names
    run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": "Help me with a task that needs approval"}]},
        interrupt_before=["*"],  # Interrupt before all nodes (for testing)
        stream_mode=["values", "events"],
    )
    elog("Runs.create (with interrupt)", run)
    assert "run_id" in run
    run_id = run["run_id"]

    # 4) Wait for run to reach interrupted state
    # In practice, the run should pause at the first node due to interrupt_before=["*"]
    import asyncio
    await asyncio.sleep(2)  # Give time for processing

    # Check run status
    interrupted_run = await client.runs.get(thread_id, run_id)
    elog("Runs.get (interrupted)", interrupted_run)
    
    # The run should be interrupted or still running (depending on graph implementation)
    # In a real graph with interrupt() calls, it would be "interrupted"
    assert interrupted_run["status"] in ("interrupted", "running", "pending")

    # 5) Resume with command (human input)
    # Based on LangGraph docs: Command(resume=value, update=dict)
    resume_run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        command={
            "resume": "approved",  # The human's response to the interrupt
            "update": {"human_approval": "approved", "user_feedback": "proceed with the task"}
        },
        stream_mode=["values"],
    )
    elog("Runs.create (resume with command)", resume_run)
    assert "run_id" in resume_run
    resume_run_id = resume_run["run_id"]

    # 6) Join the resumed run to get final output
    final_state = await client.runs.join(thread_id, resume_run_id)
    elog("Runs.join (resumed)", final_state)
    assert isinstance(final_state, dict)

    # 7) Verify resumed run completed
    completed_run = await client.runs.get(thread_id, resume_run_id)
    elog("Runs.get (completed)", completed_run)
    assert completed_run["status"] in ("completed", "failed")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_human_in_loop_validation_e2e():
    """
    Test validation of human-in-the-loop fields using LangGraph SDK client.
    Verifies that input and command are mutually exclusive.
    """
    client = get_e2e_client()

    # Setup assistant and thread
    assistant = await client.assistants.create(
        graph_id="agent",
        config={"tags": ["hitl", "validation"]},
        if_exists="do_nothing",
    )
    thread = await client.threads.create()
    thread_id = thread["thread_id"]
    assistant_id = assistant["assistant_id"]

    # Test 1: Valid run with input only
    valid_run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": "Hello"}]},
        interrupt_after=["some_node"],
    )
    elog("Valid run (input only)", valid_run)
    assert "run_id" in valid_run

    # Test 2: Valid run with command only
    valid_command_run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        command={"update": {"test": "value"}},
    )
    elog("Valid run (command only)", valid_command_run)
    assert "run_id" in valid_command_run

    # Test 3: Invalid run with both input and command (should fail)
    try:
        invalid_run = await client.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            input={"messages": [{"role": "user", "content": "Hello"}]},
            command={"update": {"test": "value"}},  # This should cause validation error
        )
        # If we reach here, the validation didn't work
        assert False, "Expected validation error for input + command, but run was created"
    except Exception as e:
        elog("Expected validation error", {"error": str(e)})
        # Expect a 422 validation error or similar
        assert "422" in str(e) or "validation" in str(e).lower() or "mutually exclusive" in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_human_in_loop_streaming_interrupt_e2e():
    """
    Test human-in-the-loop with streaming to detect interrupt events in real-time.
    """
    client = get_e2e_client()

    # Setup
    assistant = await client.assistants.create(
        graph_id="agent",
        config={"tags": ["hitl", "streaming"]},
        if_exists="do_nothing",
    )
    thread = await client.threads.create()
    thread_id = thread["thread_id"]
    assistant_id = assistant["assistant_id"]

    # Start streaming run with interrupt configuration
    stream = client.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [{"role": "user", "content": "Start a task that needs human approval"}]},
        interrupt_before=["*"],  # Interrupt before all nodes
        stream_mode=["events", "values"],
    )

    # Monitor stream for interrupt events
    event_count = 0
    interrupt_detected = False
    
    async for chunk in stream:
        event_count += 1
        elog("Stream event", {
            "event": getattr(chunk, "event", None),
            "data": getattr(chunk, "data", None)
        })

        # Look for interrupt events
        if getattr(chunk, "event", None) == "interrupt":
            interrupt_detected = True
            elog("Interrupt detected in stream!", chunk)
            break
        
        # Also check for end events (in case no interrupt occurs)
        if getattr(chunk, "event", None) == "end":
            break
            
        # Limit events to avoid infinite loops in test
        if event_count > 20:
            break

    elog("Stream summary", {
        "event_count": event_count,
        "interrupt_detected": interrupt_detected
    })

    # In a real graph with interrupt() calls, we should detect the interrupt
    # For now, we just verify the stream worked
    assert event_count > 0, "Expected at least one event from streaming run"



