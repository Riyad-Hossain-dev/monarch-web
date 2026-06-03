import json, datetime, math, random, time
from typing import Any, List, Optional
from firebase_admin import initialize_app, firestore, db
from google.cloud import firestore as google_firestore
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel

initialize_app()
router = APIRouter()

class UserRegister(BaseModel):
    uid: str
    username: str
    email: str

class UpdateAvatar(BaseModel):
    uid: str
    body: int
    hair: int
    outfit: int
    accessory: int

class AddXP(BaseModel):
    uid: str
    amount: int

class ExamSubmit(BaseModel):
    uid: str
    answer: Any

class SkillUnlock(BaseModel):
    uid: str
    skill_name: str

class StatAlloc(BaseModel):
    uid: str
    stat: str
    points: int = 1

class Challenge(BaseModel):
    challenger_uid: str
    opponent_uid: str

class Accept(BaseModel):
    battle_id: str
    opponent_uid: str

class Turn(BaseModel):
    battle_id: str
    uid: str
    action: str

def serialize(data: Any) -> Any:
    if isinstance(data, dict): return {k: serialize(v) for k, v in data.items()}
    if isinstance(data, list): return [serialize(v) for v in data]
    if isinstance(data, (datetime.datetime, datetime.date)): return data.isoformat()
    return data

@router.post("/register_user", status_code=201)
async def register_user(data: UserRegister):
    uid, username, email = data.uid, data.username, data.email
    db_fs = firestore.client()
    if len(db_fs.collection("players").where("username", "==", username.lower()).limit(1).get()) > 0:
        return Response(json.dumps({"error": "Taken"}), 409, media_type="application/json")
    player_ref = db_fs.collection("players").document(uid)
    if player_ref.get().exists: return Response(json.dumps({"error": "Exists"}), 400, media_type="application/json")
    player_data = {
        "uid": uid, "username": username.lower(), "email": email, "level": 1, "current_xp": 0, "stat_points": 0,
        "title": "Beginner", "stats": {"INT": 5, "VIT": 5, "AGI": 5, "PER": 5}, "character_type": None,
        "skills": [], "debuffs": [], "items": [], "battle_record": {"wins": 0, "losses": 0},
        "avatar": {"body": 1, "hair": 1, "outfit": 1, "accessory": 0}, "created_at": google_firestore.SERVER_TIMESTAMP
    }
    player_ref.set(player_data)
    return {"message": "Player registered successfully.", "player": serialize(player_ref.get().to_dict())}

@router.get("/get_profile")
async def get_profile(uid: str):
    doc = firestore.client().collection("players").document(uid).get()
    if not doc.exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    return serialize(doc.to_dict())

@router.post("/update_avatar")
async def update_avatar(data: UpdateAvatar):
    for v in [data.body, data.hair, data.outfit, data.accessory]:
        if v < 1 or v > 10: return Response(json.dumps({"error": "Range"}), 400, media_type="application/json")
    player_ref = firestore.client().collection("players").document(data.uid)
    if not player_ref.get().exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    avatar = {"body": data.body, "hair": data.hair, "outfit": data.outfit, "accessory": data.accessory}
    player_ref.update({"avatar": avatar})
    return avatar

@router.get("/search_player")
async def search_player(username: str):
    q = username.lower()
    docs = firestore.client().collection("players").where("username", ">=", q).where("username", "<", q + "\uf8ff").limit(20).get()
    results = []
    for d in docs:
        item = d.to_dict()
        results.append({"uid": item.get("uid"), "username": item.get("username"), "level": item.get("level"), "title": item.get("title"), "battle_record": item.get("battle_record")})
    return {"players": results}

@router.post("/add_xp")
async def add_xp(data: AddXP):
    if data.amount < 0: return Response(json.dumps({"error": "Negative"}), 400, media_type="application/json")
    player_ref = firestore.client().collection("players").document(data.uid)
    snap = player_ref.get()
    if not snap.exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    d = snap.to_dict()
    level, xp, pts, debuffs = d.get("level", 1), d.get("current_xp", 0) + data.amount, d.get("stat_points", 0), d.get("debuffs", [])
    leveled = False
    while xp >= (req_xp := math.ceil(100 * (level ** 1.5))):
        level += 1; xp -= req_xp; pts += 5; leveled = True
        if level % 10 == 0 and "job_change_pending" not in debuffs: debuffs.append("job_change_pending")
    player_ref.update({"level": level, "current_xp": xp, "stat_points": pts, "debuffs": debuffs})
    return {"new_level": level, "new_xp": xp, "xp_needed": math.ceil(100 * (level ** 1.5)), "stat_points": pts, "leveled_up": leveled}

@router.post("/trigger_exam")
async def trigger_exam(data: dict):
    uid = data.get("uid")
    if not uid: return Response(json.dumps({"error": "Missing uid"}), 400, media_type="application/json")
    player_ref = firestore.client().collection("players").document(uid)
    if not player_ref.get().exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    q = random.choice([{"id": "q1", "text": "What is 2+2?", "answer": "4"}, {"id": "q2", "text": "Shadow Monarch?", "answer": "Jin-Woo"}])
    player_ref.update({"is_locked": True, "exam_active": True, "active_exam_answer": q["answer"]})
    return {"question": q["text"], "options": ["4", "Jin-Woo", "Other"], "exam_id": q["id"]}

@router.post("/submit_exam")
async def submit_exam(data: ExamSubmit):
    player_ref = firestore.client().collection("players").document(data.uid)
    snap = player_ref.get()
    if not snap.exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    correct = str(data.answer).lower() == str(snap.to_dict().get("active_exam_answer")).lower()
    upd = {"is_locked": False, "exam_active": False, "active_exam_answer": google_firestore.DELETE_FIELD}
    if correct: upd["current_xp"] = google_firestore.Increment(100); upd["stats.INT"] = google_firestore.Increment(1)
    player_ref.update(upd)
    return {"success": correct}

@router.post("/unlock_skill")
async def unlock_skill(data: SkillUnlock):
    player_ref = firestore.client().collection("players").document(data.uid)
    snap = player_ref.get()
    if not snap.exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    d = snap.to_dict()
    skills = d.get("skills", [])
    if data.skill_name not in ["Quantum Collapse", "Acid Nova", "Axiom Break", "Regen Field", "Mind Fracture", "Soul Verse", "System Override", "Shadow Step", "Berserker Mode", "Arise"]:
        return Response(json.dumps({"error": "Invalid skill"}), 400, media_type="application/json")
    if data.skill_name not in skills:
        skills.append(data.skill_name)
        player_ref.update({"skills": skills})
    return {"skills": skills}

@router.post("/allocate_stat")
async def allocate_stat(data: StatAlloc):
    player_ref = firestore.client().collection("players").document(data.uid)
    snap = player_ref.get()
    if not snap.exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    d = snap.to_dict()
    if d.get("stat_points", 0) < data.points: return Response(json.dumps({"error": "Not enough"}), 400, media_type="application/json")
    stats = d.get("stats", {})
    if data.stat not in ["INT", "VIT", "AGI", "PER"]: return Response(json.dumps({"error": "Invalid stat"}), 400, media_type="application/json")
    stats[data.stat] = stats.get(data.stat, 5) + data.points
    player_ref.update({"stats": stats, "stat_points": d["stat_points"] - data.points})
    return {"stats": stats, "stat_points": d["stat_points"] - data.points}

@router.post("/challenge_player")
async def challenge_player(data: Challenge):
    db_fs = firestore.client()
    c_doc, o_doc = db_fs.collection("players").document(data.challenger_uid).get(), db_fs.collection("players").document(data.opponent_uid).get()
    if not c_doc.exists or not o_doc.exists: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    c_data, o_data = c_doc.to_dict(), o_doc.to_dict()
    for d in [c_data, o_data]:
        if any(x in [b.lower() for b in d.get("debuffs", [])] for x in ["shattered", "job_change_pending"]): return Response(json.dumps({"error": "debuffs"}), 400, media_type="application/json")
    bid = db.reference("battles").push().key
    battle = {
        "battle_id": bid, "turn": data.challenger_uid, "status": "waiting", "winner": None, "battle_log": [], "created_at": int(time.time() * 1000),
        "challenger": {"uid": data.challenger_uid, "username": c_data.get("username"), "hp": c_data["stats"]["VIT"]*10, "max_hp": c_data["stats"]["VIT"]*10, "stats": c_data["stats"], "skills": c_data.get("skills", []), "buffs": [], "debuffs": c_data.get("debuffs", []), "mp": 5, "max_mp": 5},
        "opponent": {"uid": data.opponent_uid, "username": o_data.get("username"), "hp": o_data["stats"]["VIT"]*10, "max_hp": o_data["stats"]["VIT"]*10, "stats": o_data["stats"], "skills": o_data.get("skills", []), "buffs": [], "debuffs": o_data.get("debuffs", []), "mp": 5, "max_mp": 5}
    }
    db.reference(f"battles/{bid}").set(battle)
    return Response(json.dumps({"battle_id": bid}), 201, media_type="application/json")

@router.post("/accept_battle")
async def accept_battle(data: Accept):
    ref = db.reference(f"battles/{data.battle_id}")
    b = ref.get()
    if not b or b["opponent"]["uid"] != data.opponent_uid or b["status"] != "waiting": return Response(json.dumps({"error": "Invalid"}), 400, media_type="application/json")
    ref.update({"status": "active"})
    b["status"] = "active"
    return b

@router.post("/execute_turn")
async def execute_turn(data: Turn):
    ref = db.reference(f"battles/{data.battle_id}")
    b = ref.get()
    if not b or b["status"] != "active" or b["turn"] != data.uid: return Response(json.dumps({"error": "Invalid"}), 400, media_type="application/json")
    atk_k, def_k = ("challenger", "opponent") if data.uid == b["challenger"]["uid"] else ("opponent", "challenger")
    atk, dfe = b[atk_k], b[def_k]
    if data.action == "attack":
        dmg = max(1, int(atk["stats"]["INT"]*1.5 - dfe["stats"]["VIT"]))
        dfe["hp"] = max(0, dfe["hp"] - dmg)
        if dfe["hp"] <= 0:
            b["status"], b["winner"] = "finished", data.uid
            db_fs = firestore.client()
            db_fs.collection("players").document(atk["uid"]).update({"battle_record.wins": google_firestore.Increment(1)})
            db_fs.collection("players").document(dfe["uid"]).update({"battle_record.losses": google_firestore.Increment(1)})
        else: b["turn"] = dfe["uid"]
    b["battle_log"].append({"actor": data.uid, "action": data.action, "timestamp": int(time.time()*1000)})
    ref.set(b)
    return b

@router.get("/get_battle_state")
async def get_battle_state(battle_id: str):
    b = db.reference(f"battles/{battle_id}").get()
    if not b: return Response(json.dumps({"error": "Not found"}), 404, media_type="application/json")
    return b
