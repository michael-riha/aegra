# Contributing to Aegra

Thank you for your interest in contributing to Aegra! 🎉

Aegra is an open source LangGraph Platform alternative, and we welcome all contributions - from bug reports to feature implementations.

## 🚀 Quick Start for Contributors

### Development Setup

1. **Fork and Clone**

   ```bash
   git clone https://github.com/YOUR_USERNAME/aegra.git
   cd aegra
   ```

2. **Install uv** (if not already installed)

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Sync Dependencies**

   ```bash
   # Sync environment and dependencies
   uv sync
   
   # Activate virtual environment
   source .venv/bin/activate  # Mac/Linux
   # OR .venv/Scripts/activate  # Windows
   ```

4. **Environment Configuration**

   ```bash
   # Copy environment file
   cp .env.example .env
   # Edit .env with your settings (API keys, etc.)
   ```

5. **Start Everything** (Database + Migrations + Server)

   ```bash
   # This starts PostgreSQL, runs migrations, and starts the server
   docker compose up aegra
   ```

6. **Verify It Works**

   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # Interactive API docs
   open http://localhost:8000/docs
   ```

7. **Run Tests** (in a separate terminal)

   ```bash
   source .venv/bin/activate
   pytest
   ```

## 🎯 How to Contribute

### 🐛 Reporting Bugs

Found a bug? Help us fix it!

1. Check if the issue already exists in our [issue tracker](https://github.com/ibbybuilds/aegra/issues)
2. If not, [create a new issue](https://github.com/ibbybuilds/aegra/issues/new) with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (Python version, OS, etc.)
   - Relevant logs or error messages

### 💡 Suggesting Features

Have an idea for Aegra? We'd love to hear it!

1. Check our [roadmap](README.md#roadmap) and existing issues
2. [Open a feature request](https://github.com/ibbybuilds/aegra/issues/new) with:
   - Clear description of the feature
   - Use case and benefits
   - Proposed implementation approach (if you have ideas)

### 🔧 Code Contributions

#### Good First Issues

New to the project? Look for issues labeled [`good first issue`](https://github.com/ibbybuilds/aegra/labels/good%20first%20issue).

#### Priority Areas

We especially welcome contributions in:

- **Agent Protocol Compliance**: Improving spec alignment
- **Authentication**: Adding JWT, OAuth, custom auth backends
- **Deployment**: Docker, Kubernetes, cloud deployment guides
- **Testing**: Unit tests, integration tests, end-to-end tests
- **Documentation**: API docs, tutorials, examples
- **Performance**: Optimization and benchmarking

#### Pull Request Process

1. **Create a Branch**

   ```bash
   git checkout -b feature/your-feature-name
   # OR
   git checkout -b fix/issue-description
   ```

2. **Make Changes**

   - Write clean, documented code
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation if needed

3. **Test Locally**

   ```bash
   # Run tests
   pytest

   # Run linting (if configured)
   # black . && isort . && flake8

   # Test the server manually
   python run_server.py
   curl http://localhost:8000/health
   ```

4. **Commit Changes**

   ```bash
   git add .
   git commit -m "feat: add awesome new feature"

   # Use conventional commits format:
   # feat: new feature
   # fix: bug fix
   # docs: documentation changes
   # test: test additions/modifications
   # refactor: code refactoring
   # chore: maintenance tasks
   ```

5. **Push and Create PR**

   ```bash
   git push origin your-branch-name
   ```

   Then create a pull request on GitHub with:

   - Clear title and description
   - Reference any related issues
   - Explain what changed and why

## 📋 Development Guidelines

### Code Style

- Follow Python PEP 8 conventions
- Use type hints where possible
- Write descriptive docstrings for functions and classes
- Keep functions focused and reasonably sized

### Testing

**All PRs must include appropriate tests.** We follow a structured testing approach:

#### Test Organization

Our test suite is organized by test type:

```
tests/
├── unit/           # Fast, isolated tests (no external dependencies)
├── integration/    # Tests with database or multiple components
└── e2e/           # End-to-end tests (full system)
```

See [tests/README.md](tests/README.md) for detailed documentation.

#### Test Requirements by PR Type

| PR Type | Required Tests | Examples |
|---------|---------------|----------|
| **New Feature** | Unit + Integration/E2E | New API endpoint → integration test |
| **Bug Fix** | Test that reproduces bug | Regression test |
| **Refactor** | Existing tests must pass | No new tests needed |
| **New Utility** | Unit tests | Pure function tests |
| **API Change** | Integration/E2E tests | Full request/response cycle |

#### Writing Tests

**Unit Tests** (`tests/unit/`):
```python
# tests/unit/test_utils/test_sse_utils.py
import pytest
from src.agent_server.utils import generate_event_id

@pytest.mark.unit
def test_generate_event_id():
    event_id = generate_event_id("run-123", 1)
    assert event_id == "run-123_event_1"
```

**Integration Tests** (`tests/integration/`):
```python
# tests/integration/test_services/test_assistant_service.py
import pytest

@pytest.mark.integration
async def test_create_assistant(test_db):
    # Test with real database
    service = AssistantService(test_db)
    assistant = await service.create_assistant(...)
    assert assistant.assistant_id is not None
```

**E2E Tests** (`tests/e2e/`):
```python
# tests/e2e/test_assistants/test_assistant_crud.py
import pytest
from tests.e2e._utils import get_e2e_client

@pytest.mark.e2e
async def test_full_assistant_workflow():
    client = get_e2e_client()
    # Test complete user workflow
    assistant = await client.assistants.create(...)
    # ... full test
```

#### Running Tests

```bash
# Run all tests
pytest

# Run by category
pytest tests/unit/          # Fast unit tests only
pytest tests/integration/   # Integration tests
pytest tests/e2e/          # E2E tests

# Run by marker
pytest -m unit              # All unit tests
pytest -m "not slow"        # Skip slow tests

# Run specific test
pytest tests/unit/test_middleware/test_double_encoded_json.py
```

#### Test Best Practices

- ✅ **Write tests first** (TDD) when fixing bugs
- ✅ **Use descriptive names**: `test_<what>_<condition>_<expected>`
- ✅ **One assertion per test** when possible
- ✅ **Use fixtures** for common setup (see `tests/conftest.py`)
- ✅ **Make tests idempotent** - use `if_exists="do_nothing"` for E2E tests
- ✅ **Clean up resources** in `finally` blocks
- ❌ **Don't skip tests** without a good reason
- ❌ **Don't test implementation details** - test behavior

### Documentation

- Update README.md if adding user-facing features
- Add docstrings to new functions and classes
- Update API documentation if changing endpoints
- Include examples for complex features

### Database Changes

- Create Alembic migrations for schema changes
- Test migrations both up and down
- Include sample data if helpful

## 🏗️ Project Structure

```
aegra/
├── src/agent_server/     # Main application code
│   ├── api/             # FastAPI route handlers
│   ├── core/            # Database, config, infrastructure
│   ├── middleware/      # Custom middleware
│   ├── models/          # Pydantic models and schemas
│   ├── services/        # Business logic layer
│   └── utils/           # Helper functions
├── graphs/              # Example agent graphs
├── tests/               # Test suite
│   ├── unit/           # Fast, isolated tests
│   ├── integration/    # Tests with DB/multiple components
│   ├── e2e/           # End-to-end tests
│   └── fixtures/      # Shared test fixtures
├── docs/                # Documentation
├── deployments/         # Docker and deployment configs
└── alembic/            # Database migrations
```

## 🆘 Getting Help

- **Questions**: Open a [discussion](https://github.com/ibbybuilds/aegra/discussions)
- **Chat**: Join our community (coming soon!)
- **Documentation**: Check the [README](README.md) and [docs](docs/)

## 🎖️ Recognition

Contributors will be:

- Listed in our README
- Mentioned in release notes for significant contributions
- Invited to join our core contributor team (for regular contributors)

## 📄 License

By contributing to Aegra, you agree that your contributions will be licensed under the Apache 2.0 License.

---

**Thank you for helping make Aegra the best open source LangGraph Platform alternative!** 🚀

_Questions? Feel free to ask in issues or discussions. We're here to help!_
