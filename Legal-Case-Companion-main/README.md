# Legal Case Companion Backend

## Project Structure

This project uses a Modular Monolith architecture built with FastAPI.

## Development Setup

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment:
   - Windows: `.\.venv\Scripts\activate`
   - Linux/macOS: `source .venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```
4. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```
5. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Available Commands

- **Run Server**: `uvicorn app.main:app --reload`
- **Run Tests**: `pytest`
- **Format Code**: `black app tests` & `isort app tests`
- **Lint Code**: `ruff check app tests`
- **Type Check**: `mypy app`
- **Create Migration**: `alembic revision --autogenerate -m "message"`
- **Apply Migrations**: `alembic upgrade head`
