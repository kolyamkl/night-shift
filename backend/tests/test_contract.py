"""The HTTP surface the frontend is built against must not drift.

tests/contract/openapi.json is the OpenAPI document of the API as the frontend (frontend/src/api.ts,
scan.ts) uses it. This test compares structure, not formatting: every path and method, its
operationId, parameters, request body, the status codes it documents, and the request schemas.
Success response bodies are left out on purpose: describing a response in more detail is allowed,
changing what is sent is not (the API tests check the bodies themselves).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.main import app

CANONICAL: dict[str, Any] = json.loads((Path(__file__).parent / "contract" / "openapi.json").read_text())
METHODS = ("get", "post", "put", "patch", "delete")
# Request bodies and their parts: what a client sends.
REQUEST_SCHEMAS = ("Ask", "Body_create_document_api_documents_post", "Correction", "Credentials", "StatusChange")


@pytest.fixture(scope="module")
def generated() -> dict[str, Any]:
    return app.openapi()


def operations(schema: dict[str, Any]) -> set[tuple[str, str]]:
    return {(method, path) for path, item in schema["paths"].items() for method in METHODS if method in item}


def test_the_same_paths_and_methods(generated):
    assert operations(generated) == operations(CANONICAL)


@pytest.mark.parametrize(("method", "path"), sorted(operations(CANONICAL)))
def test_operation_matches_the_contract(generated, method, path):
    want, got = CANONICAL["paths"][path][method], generated["paths"][path][method]
    assert got["operationId"] == want["operationId"]
    assert got.get("parameters", []) == want.get("parameters", [])
    assert got.get("requestBody") == want.get("requestBody")
    assert sorted(got["responses"]) == sorted(want["responses"])
    for status, response in want["responses"].items():
        if not status.startswith("2"):
            assert got["responses"][status] == response


@pytest.mark.parametrize("name", REQUEST_SCHEMAS)
def test_request_schemas_are_unchanged(generated, name):
    assert generated["components"]["schemas"][name] == CANONICAL["components"]["schemas"][name]
