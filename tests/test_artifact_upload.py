import hashlib

from fastapi.testclient import TestClient

from src.api.artifacts import ArtifactTooLarge, ArtifactStore, artifact_store
from src.api.server import create_app


AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def setup_function():
    artifact_store.clear()


def test_artifact_store_rejects_oversized_body_before_mutation():
    store = ArtifactStore()
    first = store.upload("build-log", b"ok", max_body_size=2)

    try:
        store.upload("build-log", b"too-large", max_body_size=4)
    except ArtifactTooLarge as exc:
        assert exc.size == 9
        assert exc.limit == 4
    else:
        raise AssertionError("oversized artifact was accepted")

    assert store.metadata("build-log") == first


def test_upload_artifact_route_accepts_body_at_limit():
    client = TestClient(create_app())
    body = b"1234"

    response = client.post(
        "/api/v2/artifacts/build-log?max_body_size=4",
        content=body,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "uploaded",
        "artifact_id": "build-log",
        "size": 4,
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def test_upload_artifact_route_rejects_oversized_body_without_state_change():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/artifacts/build-log?max_body_size=4",
        content=b"12345",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 413
    assert response.json()["detail"] == {
        "error": "artifact_too_large",
        "size": 5,
        "limit": 4,
    }
    assert artifact_store.metadata("build-log") is None
