from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exceptions import AppException
from app.main import app

# Create a temporary router to test error handling
error_test_router = APIRouter(prefix="/test-errors", tags=["test_errors"])


class SampleErrorModel(BaseModel):
    name: str
    age: int


@error_test_router.get("/app-exception")
def raise_app_exception():
    raise AppException(
        status_code=400, code="TEST_APP_ERROR", message="This is an app exception"
    )


@error_test_router.get("/http-exception")
def raise_http_exception():
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="This is an http exception")


@error_test_router.post("/validation-error")
def raise_validation_error(model: SampleErrorModel):
    return {"message": "success"}


@error_test_router.get("/unhandled-exception")
def raise_unhandled_exception():
    raise RuntimeError("This is an unhandled exception")


app.include_router(error_test_router)

client = TestClient(app, raise_server_exceptions=False)


def test_app_exception_contract():
    response = client.get("/test-errors/app-exception")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "TEST_APP_ERROR"
    assert error["message"] == "This is an app exception"
    assert error["details"] is None
    assert "request_id" in error


def test_http_exception_contract():
    response = client.get("/test-errors/http-exception")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "HTTP_ERROR"
    assert error["message"] == "This is an http exception"
    assert error["details"] is None
    assert "request_id" in error


def test_validation_error_contract():
    response = client.post(
        "/test-errors/validation-error", json={"name": "John"}
    )  # Missing age
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "The request contains invalid or missing fields."
    assert isinstance(error["details"], list)
    assert "request_id" in error


def test_unhandled_exception_contract():
    response = client.get("/test-errors/unhandled-exception")
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert error["message"] == "An unexpected error occurred."
    assert error["details"] is None
    assert "request_id" in error
