"""Integration tests for runs CRUD operations"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from agent_server.core.orm import get_session as core_get_session
from tests.fixtures.clients import create_test_app, make_client
from tests.fixtures.database import DummySessionBase, override_get_session_dep


def _thread_row(
    thread_id="test-thread-123", status="idle", metadata=None, user_id="test-user"
):
    """Create a mock thread ORM object"""

    class DummyThread:
        def __init__(self):
            self.thread_id = thread_id
            self.status = status
            self.metadata_json = metadata or {}
            self.metadata = self.metadata_json
            self.user_id = user_id
            self.created_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

            class _Col:
                def __init__(self, name):
                    self.name = name

            class _T:
                columns = [
                    _Col("thread_id"),
                    _Col("status"),
                    _Col("metadata"),
                    _Col("user_id"),
                    _Col("created_at"),
                    _Col("updated_at"),
                ]

            self.__table__ = _T()

    return DummyThread()


def _assistant_row(
    assistant_id="test-assistant-123", graph_id="test-graph", user_id="test-user"
):
    """Create a mock assistant ORM object"""

    class DummyAssistant:
        def __init__(self):
            self.assistant_id = assistant_id
            self.graph_id = graph_id
            self.user_id = user_id

    return DummyAssistant()


def _run_row(
    run_id="test-run-123",
    thread_id="test-thread-123",
    assistant_id="test-assistant-123",
    status="running",
    user_id="test-user",
    metadata=None,
    input_data=None,
    output_data=None,
):
    """Create a mock run ORM object"""

    class DummyRun:
        def __init__(self):
            self.run_id = run_id
            self.thread_id = thread_id
            self.assistant_id = assistant_id
            self.status = status
            self.user_id = user_id
            self.metadata_json = metadata or {}
            self.metadata = (
                self.metadata_json
            )  # Some endpoints access metadata directly
            self.input = input_data or {"message": "test"}
            self.output = output_data
            self.error_message = None
            self.config = {}
            self.context = {}
            self.created_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

            class _Col:
                def __init__(self, name):
                    self.name = name

            class _T:
                columns = [
                    _Col("run_id"),
                    _Col("thread_id"),
                    _Col("assistant_id"),
                    _Col("status"),
                    _Col("user_id"),
                    _Col("metadata"),
                    _Col("input"),
                    _Col("output"),
                    _Col("error_message"),
                    _Col("config"),
                    _Col("context"),
                    _Col("created_at"),
                    _Col("updated_at"),
                ]

            self.__table__ = _T()

    return DummyRun()


class TestCreateRun:
    """Test POST /threads/{thread_id}/runs"""

    def test_create_run_validation_error_no_input_or_command(self):
        """Test that run creation requires either input or command"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            pass

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.post(
            "/threads/test-thread-123/runs",
            json={"assistant_id": "asst-123"},
        )

        # Should get validation error (422) for missing input/command
        assert resp.status_code == 422


class TestGetRun:
    """Test GET /threads/{thread_id}/runs/{run_id}"""

    def test_get_run_success(self):
        """Test getting an existing run"""
        app = create_test_app(include_runs=True, include_threads=False)

        run = _run_row(status="completed")

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return run

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs/test-run-123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "test-run-123"
        assert data["thread_id"] == "test-thread-123"
        assert data["status"] == "completed"

    def test_get_run_not_found(self):
        """Test getting a non-existent run"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return None

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs/nonexistent")

        assert resp.status_code == 404


class TestListRuns:
    """Test GET /threads/{thread_id}/runs"""

    def test_list_runs_success(self):
        """Test listing runs for a thread"""
        app = create_test_app(include_runs=True, include_threads=False)

        runs = [
            _run_row("run-1", status="completed"),
            _run_row("run-2", status="running"),
            _run_row("run-3", status="pending"),
        ]

        class Session(DummySessionBase):
            async def scalars(self, _stmt):
                class Result:
                    def all(self):
                        return runs

                return Result()

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["run_id"] == "run-1"

    def test_list_runs_empty(self):
        """Test listing runs when thread has none"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            async def scalars(self, _stmt):
                class Result:
                    def all(self):
                        return []

                return Result()

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs")

        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_list_runs_with_limit(self):
        """Test listing runs with limit parameter"""
        app = create_test_app(include_runs=True, include_threads=False)

        runs = [_run_row(f"run-{i}") for i in range(5)]

        class Session(DummySessionBase):
            async def scalars(self, _stmt):
                class Result:
                    def all(self):
                        return runs[:2]  # Simulate limit

                return Result()

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs?limit=2")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 5

    def test_list_runs_with_offset(self):
        """Test listing runs with offset parameter"""
        app = create_test_app(include_runs=True, include_threads=False)

        runs = [_run_row(f"run-{i}") for i in range(10)]

        class Session(DummySessionBase):
            async def scalars(self, _stmt):
                class Result:
                    def all(self):
                        return runs[5:]  # Simulate offset

                return Result()

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs?offset=5")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestUpdateRun:
    """Test PATCH /threads/{thread_id}/runs/{run_id}"""

    def test_update_run_validation(self):
        """Test updating run requires valid payload"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            pass

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        # Empty update should fail validation
        resp = client.patch(
            "/threads/test-thread-123/runs/test-run-123",
            json={},
        )

        assert resp.status_code == 422


class TestCancelRun:
    """Test POST /threads/{thread_id}/runs/{run_id}/cancel"""

    def test_cancel_run_not_found(self):
        """Test canceling a non-existent run"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return None

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.post("/threads/test-thread-123/runs/nonexistent/cancel")

        assert resp.status_code == 404

    def test_cancel_run_success(self):
        """Test successfully canceling a run"""
        app = create_test_app(include_runs=True, include_threads=False)

        run = _run_row(status="running")

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return run

            async def execute(self, _stmt):
                pass

            async def commit(self):
                pass

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        with patch("agent_server.api.runs.streaming_service") as mock_streaming:
            mock_streaming.cancel_run = AsyncMock()

            resp = client.post("/threads/test-thread-123/runs/test-run-123/cancel")

            assert resp.status_code == 200


class TestDeleteRun:
    """Test DELETE /threads/{thread_id}/runs/{run_id}"""

    def test_delete_run_not_found(self):
        """Test deleting a non-existent run"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return None

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.delete("/threads/test-thread-123/runs/nonexistent")

        assert resp.status_code == 404

    def test_delete_run_active_not_allowed(self):
        """Test deleting an active run is not allowed"""
        app = create_test_app(include_runs=True, include_threads=False)

        run = _run_row(status="running")

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return run

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.delete("/threads/test-thread-123/runs/test-run-123")

        # Should return error (400, 409, etc.) for active run
        assert resp.status_code >= 400
        assert resp.status_code < 500

    def test_delete_run_success(self):
        """Test successfully deleting a completed run"""
        app = create_test_app(include_runs=True, include_threads=False)

        run = _run_row(status="completed")

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return run

            async def execute(self, _stmt):
                pass

            async def commit(self):
                pass

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.delete("/threads/test-thread-123/runs/test-run-123")

        assert resp.status_code == 204


class TestJoinRun:
    """Test GET /threads/{thread_id}/runs/{run_id}/join"""

    def test_join_run_not_found(self):
        """Test joining a non-existent run"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return None

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs/nonexistent/join")

        assert resp.status_code == 404

    def test_join_run_already_completed(self):
        """Test joining an already completed run"""
        app = create_test_app(include_runs=True, include_threads=False)

        run = _run_row(status="completed")

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return run

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs/test-run-123/join")

        assert resp.status_code == 200
        # Response may vary depending on run state
        assert isinstance(resp.json(), (dict, list))


class TestStreamRun:
    """Test GET /threads/{thread_id}/runs/{run_id}/stream"""

    def test_stream_run_not_found(self):
        """Test streaming a non-existent run"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            async def scalar(self, _stmt):
                return None

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs/nonexistent/stream")

        assert resp.status_code == 404


class TestRunWithInput:
    """Test creating runs with input vs command"""

    def test_create_run_with_input_validation(self):
        """Test creating run with input passes validation"""
        app = create_test_app(include_runs=True, include_threads=False)

        class Session(DummySessionBase):
            pass

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.post(
            "/threads/test-thread-123/runs",
            json={
                "assistant_id": "test-assistant-123",
                "input": {"message": "Hello"},
            },
        )

        # Should not be a validation error
        assert resp.status_code != 422


class TestRunStatuses:
    """Test filtering runs by status"""

    def test_list_runs_filter_by_status(self):
        """Test filtering runs by status"""
        app = create_test_app(include_runs=True, include_threads=False)

        runs = [
            _run_row("run-1", status="completed"),
            _run_row("run-2", status="completed"),
        ]

        class Session(DummySessionBase):
            async def scalars(self, _stmt):
                class Result:
                    def all(self):
                        return runs

                return Result()

        app.dependency_overrides[core_get_session] = override_get_session_dep(Session)
        client = make_client(app)

        resp = client.get("/threads/test-thread-123/runs?status=completed")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
