import httpx
import pytest
from fastapi.testclient import TestClient

from app.database import initialize_database
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDENTS_DB_PATH", str(tmp_path / "students.sqlite3"))
    initialize_database()
    with TestClient(app) as test_client:
        yield test_client


def student_payload(**overrides):
    return {
        "name": "Asha Rao",
        "date_of_birth": "2005-04-12",
        "email": "asha@example.com",
        "phone": "+1 555 0100",
        "course": "Computer Science",
        "address": "12 Sample Street",
        "enrollment_date": "2024-08-20",
        **overrides,
    }


def test_crud_lifecycle_and_persistence(client):
    created = client.post("/students", json=student_payload())
    assert created.status_code == 201
    student = created.json()
    assert student["id"] == 1
    assert student["date_of_birth"] == "2005-04-12"

    assert client.get("/students").json() == [student]
    assert client.get("/students/1").json() == student
    assert client.get("/students?course=computer&born_after=2004-01-01").json() == [
        student
    ]
    assert client.get("/students?born_after=2005-04-12").json() == []

    updated = client.patch("/students/1", json={"course": "Data Science"})
    assert updated.status_code == 200
    assert updated.json()["course"] == "Data Science"
    assert updated.json()["name"] == "Asha Rao"

    replaced = client.put(
        "/students/1",
        json={
            "name": "Asha R.",
            "date_of_birth": "2005-04-12",
            "phone": "+1 555 0101",
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["name"] == "Asha R."
    assert replaced.json()["email"] is None

    with TestClient(app) as reopened_client:
        assert reopened_client.get("/students/1").json()["name"] == "Asha R."

    deleted = client.delete("/students/1")
    assert deleted.status_code == 204
    assert client.get("/students/1").status_code == 404
    assert client.delete("/students/1").status_code == 404


def test_validation_conflicts_and_missing_records(client):
    assert client.post("/students", json={"name": "No contact"}).status_code == 422
    assert client.post(
        "/students",
        json=student_payload(date_of_birth="not-a-date"),
    ).status_code == 422

    assert client.post("/students", json=student_payload()).status_code == 201
    duplicate = client.post(
        "/students",
        json=student_payload(name="Another Student"),
    )
    assert duplicate.status_code == 409
    assert client.patch("/students/999", json={"course": "Math"}).status_code == 404
    assert client.put("/students/999", json=student_payload()).status_code == 404


def test_patch_preserves_contact_requirement_and_rejects_empty_patch(client):
    client.post("/students", json=student_payload(phone=None))
    assert client.patch("/students/1", json={"email": None}).status_code == 422
    assert client.patch("/students/1", json={}).status_code == 422
    assert client.patch("/students/1", json={"name": None}).status_code == 422
    assert (
        client.patch("/students/1", json={"date_of_birth": None}).status_code == 422
    )
    assert (
        client.post("/students", json=student_payload(unknown_field="ignored")).status_code
        == 422
    )


def test_ollama_question_uses_filtered_database_context(client, monkeypatch):
    client.post(
        "/students",
        json=student_payload(name="Older", date_of_birth="2005-04-12"),
    )
    client.post(
        "/students",
        json=student_payload(
            name="Younger",
            email="younger@example.com",
            date_of_birth="2006-02-03",
        ),
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "There is 1 matching student."}}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        return FakeResponse()

    monkeypatch.setattr("app.ollama.httpx.post", fake_post)
    response = client.post(
        "/ask",
        json={"question": "List students born after 2005."},
    )

    assert response.status_code == 200
    assert response.json()["matching_student_count"] == 1
    assert response.json()["records_considered"] == 1
    assert captured["url"] == "http://localhost:11434/api/chat"
    prompt = captured["payload"]["messages"][1]["content"]
    assert "Younger" in prompt
    assert "Older" not in prompt
    assert "younger@example.com" not in prompt
    assert "12 Sample Street" not in prompt


def test_ollama_count_context_and_unavailable_service(client, monkeypatch):
    client.post("/students", json=student_payload())
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "There is 1 student."}}

    def fake_post(url, **kwargs):
        captured["payload"] = kwargs["json"]
        return FakeResponse()

    monkeypatch.setattr("app.ollama.httpx.post", fake_post)
    response = client.post("/ask", json={"question": "How many students are there?"})
    assert response.status_code == 200
    assert response.json()["matching_student_count"] == 1
    assert response.json()["records_considered"] == 0
    prompt = captured["payload"]["messages"][1]["content"]
    assert '"matching_student_count": 1' in prompt
    assert '"students": []' in prompt

    def unavailable(url, **kwargs):
        raise httpx.ConnectError("service unavailable")

    monkeypatch.setattr("app.ollama.httpx.post", unavailable)
    unavailable_response = client.post(
        "/ask", json={"question": "How many students are there?"}
    )
    assert unavailable_response.status_code == 503
    assert client.post("/ask", json={"question": "  "}).status_code == 422
