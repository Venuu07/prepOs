# tests/test_api.py
#
# WHAT: Integration tests that send real HTTP requests to the FastAPI app.
# WHY: Tests prove your endpoints work end-to-end, catch regressions,
#      and are a concrete requirement for the resume claim about testing.
#
# HOW IT WORKS:
# TestClient wraps the FastAPI app and lets you make HTTP calls without
# starting a real server. It's synchronous — no asyncio needed in tests.
#
# IMPORTANT: These tests hit the REAL Neon database.
# For a production project, you'd use a separate test database.
# For now, real DB is fine — it validates your schema and queries are correct.
#
# Run with: backend\.venv\Scripts\pytest.exe tests/ -v

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


# ── Helper: create a test subject ─────────────────────────────────────────────
def create_test_subject(name: str = "Test Subject") -> dict:
    response = client.post("/api/v1/subjects", json={"name": name, "short_code": "TS"})
    return response.json()


# ── Health Check ──────────────────────────────────────────────────────────────

def test_health_check():
    """The /health endpoint should always return 200."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ── Subject Tests ─────────────────────────────────────────────────────────────

def test_create_subject():
    """POST /api/v1/subjects creates a subject and returns 201."""
    response = client.post("/api/v1/subjects", json={
        "name": "Operating Systems Test",
        "short_code": "OST",
        "description": "Test subject for OS",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Operating Systems Test"
    assert data["short_code"] == "OST"
    assert data["is_active"] is True
    assert "id" in data

    # Cleanup
    client.delete(f"/api/v1/subjects/{data['id']}")


def test_create_subject_duplicate_name():
    """Creating a subject with a duplicate name returns 409 Conflict."""
    unique_name = "DuplicateTest Subject"
    r1 = client.post("/api/v1/subjects", json={"name": unique_name})
    assert r1.status_code == 201

    r2 = client.post("/api/v1/subjects", json={"name": unique_name})
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"]

    # Cleanup
    client.delete(f"/api/v1/subjects/{r1.json()['id']}")


def test_get_subject_not_found():
    """GET /api/v1/subjects/99999 returns 404."""
    response = client.get("/api/v1/subjects/99999")
    assert response.status_code == 404


# ── Topic Tests ───────────────────────────────────────────────────────────────

def test_create_topic():
    """POST /api/v1/topics creates a topic under a subject."""
    # First create a subject
    subject = client.post("/api/v1/subjects", json={"name": "DSA For Test"}).json()

    response = client.post("/api/v1/topics", json={
        "subject_id": subject["id"],
        "name": "Binary Search",
        "difficulty": "MEDIUM",
        "is_gate_relevant": False,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Binary Search"
    assert data["subject_id"] == subject["id"]
    assert data["difficulty"] == "MEDIUM"

    # Cleanup (subject cascade deletes topic)
    client.delete(f"/api/v1/subjects/{subject['id']}")


def test_list_topics_by_subject():
    """GET /api/v1/topics?subject_id=X returns only that subject's topics."""
    subject = client.post("/api/v1/subjects", json={"name": "Filtered Subject Test"}).json()

    client.post("/api/v1/topics", json={"subject_id": subject["id"], "name": "Topic A"})
    client.post("/api/v1/topics", json={"subject_id": subject["id"], "name": "Topic B"})

    response = client.get(f"/api/v1/topics?subject_id={subject['id']}")
    assert response.status_code == 200
    topics = response.json()
    assert len(topics) == 2
    names = {t["name"] for t in topics}
    assert "Topic A" in names
    assert "Topic B" in names

    # Cleanup
    client.delete(f"/api/v1/subjects/{subject['id']}")


# ── Goal Tests ────────────────────────────────────────────────────────────────

def test_create_goal():
    """POST /api/v1/goals creates a goal."""
    response = client.post("/api/v1/goals", json={
        "user_id": 1,
        "title": "Crack EPAM Placement",
        "goal_type": "PLACEMENT",
        "priority": "HIGH",
        "target_date": "2026-10-15",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Crack EPAM Placement"
    assert data["goal_type"] == "PLACEMENT"
    assert data["status"] == "ACTIVE"
    assert data["target_date"] == "2026-10-15"

    # Cleanup
    client.delete(f"/api/v1/goals/{data['id']}")


def test_create_goal_invalid_type():
    """Goal with an invalid goal_type returns 422 Unprocessable Entity."""
    response = client.post("/api/v1/goals", json={
        "user_id": 1,
        "title": "Invalid Goal",
        "goal_type": "INVALID_TYPE",
    })
    assert response.status_code == 422  # Pydantic validation fails


def test_update_goal_status():
    """PATCH /api/v1/goals/{id} can mark a goal as ACHIEVED."""
    goal = client.post("/api/v1/goals", json={
        "user_id": 1,
        "title": "Goal To Achieve",
        "goal_type": "PLACEMENT",
    }).json()

    response = client.patch(f"/api/v1/goals/{goal['id']}", json={"status": "ACHIEVED"})
    assert response.status_code == 200
    assert response.json()["status"] == "ACHIEVED"

    # Cleanup
    client.delete(f"/api/v1/goals/{goal['id']}")


# ── Problem Tests ─────────────────────────────────────────────────────────────

def test_create_problem():
    """POST /api/v1/problems creates a problem."""
    response = client.post("/api/v1/problems", json={
        "user_id": 1,
        "title": "Two Sum",
        "platform": "LEETCODE",
        "difficulty": "EASY",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Two Sum"
    assert data["status"] == "NOT_STARTED"
    assert data["confidence"] == "LOW"

    # Cleanup
    client.delete(f"/api/v1/problems/{data['id']}")
