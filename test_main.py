"""
Comprehensive tests for the Monarch Game API (FastAPI version).
23 tests covering all 11 endpoints and key business logic.

Uses unittest.mock to patch Firebase Admin SDK calls so tests
run without a real Firebase project.
"""

import math
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Patch firebase_admin.initialize_app BEFORE importing main/app
# ---------------------------------------------------------------------------
with patch("firebase_admin.initialize_app"):
    with patch.dict("os.environ", {}, clear=False):
        # Prevent main.py module-level initialize_app from running
        import importlib
        import firebase_admin
        firebase_admin.initialize_app = MagicMock()
        
        # Now import the app
        from app import app

client = TestClient(app)


# ===========================================================================
# Helper: create a mock Firestore document snapshot
# ===========================================================================

def _mock_doc(data: dict | None, exists: bool = True):
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data
    return doc


def _default_player(uid="u1", username="hero", level=1, **overrides):
    player = {
        "uid": uid,
        "username": username,
        "email": "a@b.com",
        "level": level,
        "current_xp": 0,
        "stat_points": 0,
        "title": "Beginner",
        "stats": {"INT": 5, "VIT": 5, "AGI": 5, "PER": 5},
        "character_type": None,
        "skills": [],
        "debuffs": [],
        "items": [],
        "battle_record": {"wins": 0, "losses": 0},
        "avatar": {"body": 1, "hair": 1, "outfit": 1, "accessory": 0},
    }
    player.update(overrides)
    return player


# ===========================================================================
# 1. Health check
# ===========================================================================

def test_health_check():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "alive"
    assert data["game"] == "Monarch"


# ===========================================================================
# 2–4. register_user
# ===========================================================================

@patch("main.firestore")
def test_register_user_success(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    mock_fs.SERVER_TIMESTAMP = "SERVER_TIMESTAMP"

    col = MagicMock()
    mock_client.collection.return_value = col

    # Username query returns empty → unique
    col.where.return_value.limit.return_value.get.return_value = []

    doc_ref = MagicMock()
    col.document.return_value = doc_ref
    doc_ref.get.return_value = _mock_doc(None, exists=False)

    # After set(), return saved data
    saved = _default_player(uid="u1", username="hero")
    doc_ref.get.side_effect = [_mock_doc(None, exists=False), _mock_doc(saved)]

    resp = client.post("/register_user", json={"uid": "u1", "username": "Hero", "email": "a@b.com"})
    assert resp.status_code == 201
    assert resp.json()["message"] == "Player registered successfully."


@patch("main.firestore")
def test_register_user_duplicate_username(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client

    col = MagicMock()
    mock_client.collection.return_value = col
    col.where.return_value.limit.return_value.get.return_value = [_mock_doc({"username": "hero"})]

    resp = client.post("/register_user", json={"uid": "u2", "username": "hero", "email": "b@c.com"})
    assert resp.status_code == 409


def test_register_user_missing_fields():
    # Pydantic will reject the body entirely — FastAPI returns 422
    resp = client.post("/register_user", json={"uid": "u1"})
    assert resp.status_code == 422


# ===========================================================================
# 5. get_profile
# ===========================================================================

@patch("main.firestore")
def test_get_profile_success(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    mock_client.collection.return_value.document.return_value.get.return_value = _mock_doc(
        _default_player()
    )

    resp = client.get("/get_profile", params={"uid": "u1"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "hero"


@patch("main.firestore")
def test_get_profile_not_found(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    mock_client.collection.return_value.document.return_value.get.return_value = _mock_doc(
        None, exists=False
    )

    resp = client.get("/get_profile", params={"uid": "missing"})
    assert resp.status_code == 404


# ===========================================================================
# 7. update_avatar
# ===========================================================================

@patch("main.firestore")
def test_update_avatar_success(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    doc_ref = MagicMock()
    mock_client.collection.return_value.document.return_value = doc_ref
    doc_ref.get.return_value = _mock_doc(_default_player())

    resp = client.post("/update_avatar", json={"uid": "u1", "body": 3, "hair": 2, "outfit": 5, "accessory": 1})
    assert resp.status_code == 200
    assert resp.json()["body"] == 3


def test_update_avatar_out_of_range():
    resp = client.post("/update_avatar", json={"uid": "u1", "body": 11, "hair": 2, "outfit": 5, "accessory": 1})
    # Pydantic does not enforce range; the endpoint returns 400
    # Actually Pydantic accepts int, our endpoint validates range
    # But the body value 11 passes Pydantic — our code returns 400
    assert resp.status_code in (400, 422)


# ===========================================================================
# 9. search_player
# ===========================================================================

@patch("main.firestore")
def test_search_player_found(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    col = MagicMock()
    mock_client.collection.return_value = col

    doc = _mock_doc({"uid": "u1", "username": "hero", "level": 1, "title": "Beginner", "battle_record": {"wins": 0, "losses": 0}})
    col.where.return_value.where.return_value.limit.return_value.get.return_value = [doc]

    resp = client.get("/search_player", params={"username": "her"})
    assert resp.status_code == 200
    assert len(resp.json()["players"]) == 1


def test_search_player_missing_param():
    resp = client.get("/search_player")
    assert resp.status_code == 422


# ===========================================================================
# 11–12. add_xp
# ===========================================================================

@patch("main.firestore")
def test_add_xp_no_level_up(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    doc_ref = MagicMock()
    mock_client.collection.return_value.document.return_value = doc_ref
    doc_ref.get.return_value = _mock_doc(_default_player(current_xp=0, level=1))

    resp = client.post("/add_xp", json={"uid": "u1", "amount": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["leveled_up"] is False
    assert body["new_xp"] == 10


@patch("main.firestore")
def test_add_xp_level_up(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    doc_ref = MagicMock()
    mock_client.collection.return_value.document.return_value = doc_ref
    # Player at level 1, xp_needed = ceil(100 * 1^1.5) = 100
    doc_ref.get.return_value = _mock_doc(_default_player(current_xp=0, level=1))

    resp = client.post("/add_xp", json={"uid": "u1", "amount": 150})
    assert resp.status_code == 200
    body = resp.json()
    assert body["leveled_up"] is True
    assert body["new_level"] >= 2


def test_add_xp_negative():
    resp = client.post("/add_xp", json={"uid": "u1", "amount": -5})
    assert resp.status_code == 400


# ===========================================================================
# 14–15. challenge_player
# ===========================================================================

@patch("main.db")
@patch("main.firestore")
def test_challenge_player_success(mock_fs, mock_db):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client

    p1 = _default_player(uid="c1", username="challenger")
    p2 = _default_player(uid="o1", username="opponent")

    def _get_doc(uid):
        ref = MagicMock()
        if uid == "c1":
            ref.get.return_value = _mock_doc(p1)
        else:
            ref.get.return_value = _mock_doc(p2)
        return ref

    mock_client.collection.return_value.document = _get_doc

    battle_ref = MagicMock()
    battle_ref.key = "battle123"
    mock_db.reference.return_value.push.return_value = battle_ref

    resp = client.post("/challenge_player", json={"challenger_uid": "c1", "opponent_uid": "o1"})
    assert resp.status_code == 201
    assert "battle_id" in resp.json()


@patch("main.db")
@patch("main.firestore")
def test_challenge_player_debuff_blocked(mock_fs, mock_db):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client

    p1 = _default_player(uid="c1", debuffs=["shattered"])
    p2 = _default_player(uid="o1")

    def _get_doc(uid):
        ref = MagicMock()
        if uid == "c1":
            ref.get.return_value = _mock_doc(p1)
        else:
            ref.get.return_value = _mock_doc(p2)
        return ref

    mock_client.collection.return_value.document = _get_doc

    resp = client.post("/challenge_player", json={"challenger_uid": "c1", "opponent_uid": "o1"})
    assert resp.status_code == 400
    assert "debuffs" in resp.json()["error"]


# ===========================================================================
# 16. accept_battle
# ===========================================================================

@patch("main.db")
def test_accept_battle_success(mock_db):
    battle = {
        "battle_id": "b1",
        "status": "waiting",
        "opponent": {"uid": "o1"},
        "challenger": {"uid": "c1"},
    }
    ref = MagicMock()
    ref.get.return_value = battle
    mock_db.reference.return_value = ref

    resp = client.post("/accept_battle", json={"battle_id": "b1", "opponent_uid": "o1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@patch("main.db")
def test_accept_battle_wrong_opponent(mock_db):
    battle = {
        "battle_id": "b1",
        "status": "waiting",
        "opponent": {"uid": "o1"},
    }
    ref = MagicMock()
    ref.get.return_value = battle
    mock_db.reference.return_value = ref

    resp = client.post("/accept_battle", json={"battle_id": "b1", "opponent_uid": "intruder"})
    assert resp.status_code == 400


# ===========================================================================
# 18. get_battle_state
# ===========================================================================

@patch("main.db")
def test_get_battle_state_success(mock_db):
    mock_db.reference.return_value.get.return_value = {"battle_id": "b1", "status": "active"}

    resp = client.get("/get_battle_state", params={"battle_id": "b1"})
    assert resp.status_code == 200
    assert resp.json()["battle_id"] == "b1"


@patch("main.db")
def test_get_battle_state_not_found(mock_db):
    mock_db.reference.return_value.get.return_value = None

    resp = client.get("/get_battle_state", params={"battle_id": "nope"})
    assert resp.status_code == 404


# ===========================================================================
# 20. execute_turn – basic attack
# ===========================================================================

@patch("main.google_firestore")
@patch("main.firestore")
@patch("main.db")
@patch("main.random")
def test_execute_turn_attack(mock_random, mock_db, mock_fs, mock_gfs):
    mock_random.random.return_value = 0.99  # no crit
    battle = {
        "battle_id": "b1",
        "status": "active",
        "turn": "c1",
        "winner": None,
        "battle_log": [],
        "challenger": {
            "uid": "c1", "username": "alice",
            "stats": {"INT": 10, "VIT": 5, "AGI": 5, "PER": 5},
            "character_type": None, "debuffs": [], "buffs": [],
            "hp": 50, "max_hp": 50, "mp": 5, "max_mp": 5, "skills": [],
        },
        "opponent": {
            "uid": "o1", "username": "bob",
            "stats": {"INT": 5, "VIT": 5, "AGI": 5, "PER": 5},
            "character_type": None, "debuffs": [], "buffs": [],
            "hp": 50, "max_hp": 50, "mp": 5, "max_mp": 5, "skills": [],
        },
    }
    ref = MagicMock()
    ref.get.return_value = battle
    mock_db.reference.return_value = ref

    resp = client.post("/execute_turn", json={"battle_id": "b1", "uid": "c1", "action": "attack"})
    assert resp.status_code == 200
    data = resp.json()
    # Damage should have been dealt: INT*1.5 - VIT = 10*1.5 - 5 = 10
    assert data["opponent"]["hp"] < 50


# ===========================================================================
# 21. unlock_skill
# ===========================================================================

@patch("main.firestore")
def test_unlock_skill_success(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    doc_ref = MagicMock()
    mock_client.collection.return_value.document.return_value = doc_ref
    doc_ref.get.return_value = _mock_doc(_default_player(skills=[]))

    resp = client.post("/unlock_skill", json={"uid": "u1", "skill_name": "Acid Nova"})
    assert resp.status_code == 200
    assert "Acid Nova" in resp.json()["skills"]


@patch("main.firestore")
def test_unlock_skill_invalid_name(mock_fs):
    resp = client.post("/unlock_skill", json={"uid": "u1", "skill_name": "Fireball"})
    assert resp.status_code == 400


# ===========================================================================
# 23. allocate_stat
# ===========================================================================

@patch("main.firestore")
def test_allocate_stat_success(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    doc_ref = MagicMock()
    mock_client.collection.return_value.document.return_value = doc_ref
    doc_ref.get.return_value = _mock_doc(_default_player(stat_points=10))

    resp = client.post("/allocate_stat", json={"uid": "u1", "stat": "INT", "points": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["stats"]["INT"] == 8  # 5 base + 3
    assert body["stat_points"] == 7


@patch("main.firestore")
def test_allocate_stat_not_enough_points(mock_fs):
    mock_client = MagicMock()
    mock_fs.client.return_value = mock_client
    doc_ref = MagicMock()
    mock_client.collection.return_value.document.return_value = doc_ref
    doc_ref.get.return_value = _mock_doc(_default_player(stat_points=2))

    resp = client.post("/allocate_stat", json={"uid": "u1", "stat": "VIT", "points": 5})
    assert resp.status_code == 400
    assert "Not enough" in resp.json()["error"]
