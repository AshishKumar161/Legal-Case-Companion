import json
import os
import sys

# Add backend directory to sys.path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.openapi.utils import get_openapi

from app.main import app


def generate_schema():
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    output_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "docs", "openapi.json")
    )
    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"OpenAPI schema generated at: {output_path}")


if __name__ == "__main__":
    generate_schema()
