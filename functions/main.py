# Welcome to Cloud Functions for Firebase for Python!
# Deploy with `firebase deploy`

import json
import datetime
import math
import random
import time
from typing import Any
from firebase_functions import https_fn, options
from firebase_functions.options import set_global_options
from firebase_admin import initialize_app, firestore, db
from google.cloud import firestore as google_firestore

# Set global options for instance scaling
set_global_options(max_instances=10)

# Initialize Firebase Admin SDK
initialize_app()

# Configure CORS Options to allow all origins and standard methods
cors_opt = options.CorsOptions(
    cors_origins=["*"],
    cors_methods=["GET", "POST", "OPTIONS"]
)

def serialize_firestore_data(data: Any) -> Any:
    """
    Recursively processes data to make it JSON serializable.
    Converts datetime objects to ISO format strings.
    """
    if isinstance(data, dict):
        return {k: serialize_firestore_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_firestore_data(v) for v in data]
    elif isinstance(data, (datetime.datetime, datetime.date)):
        return data.isoformat()
    return data

@https_fn.on_request(cors=cors_opt)
def register_user(req: https_fn.Request) -> https_fn.Response:
    """
    POST: Registers a new user/player profile.
    Takes: username, email, uid
    Stores in 'players' collection with document ID 'uid'.
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)
        
    if req.method != "POST":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use POST."}),
            status=405,
            mimetype="application/json"
        )

    try:
        body = req.get_json(silent=True)
    except Exception:
        body = None

    if not body:
        return https_fn.Response(
            json.dumps({"error": "Invalid or missing JSON request body."}),
            status=400,
            mimetype="application/json"
        )

    uid = body.get("uid")
    username = body.get("username")
    email = body.get("email")

    # Input validations
    if not uid or not username or not email:
        return https_fn.Response(
            json.dumps({"error": "Missing required fields: uid, username, email"}),
            status=400,
            mimetype="application/json"
        )

    if not isinstance(uid, str) or not isinstance(username, str) or not isinstance(email, str):
        return https_fn.Response(
            json.dumps({"error": "Fields uid, username, email must be strings."}),
            status=400,
            mimetype="application/json"
        )

    username_lower = username.strip().lower()
    if not username_lower:
        return https_fn.Response(
            json.dumps({"error": "Username cannot be empty or whitespace only."}),
            status=400,
            mimetype="application/json"
        )

    db_firestore = firestore.client()
    players_ref = db_firestore.collection("players")

    # Check if username is unique
    username_query = players_ref.where("username", "==", username_lower).limit(1).get()
    if len(username_query) > 0:
        return https_fn.Response(
            json.dumps({"error": "Username is already taken."}),
            status=409,
            mimetype="application/json"
        )

    # Check if player document with this uid already exists
    player_ref = players_ref.document(uid)
    if player_ref.get().exists:
        return https_fn.Response(
            json.dumps({"error": "Player with this UID is already registered."}),
            status=400,
            mimetype="application/json"
        )

    # Store player profile
    player_data = {
        "uid": uid,
        "username": username_lower,
        "email": email.strip(),
        "level": 1,
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
        "created_at": firestore.SERVER_TIMESTAMP
    }

    player_ref.set(player_data)

    # Fetch saved document to return actual server timestamp
    saved_doc = player_ref.get()
    saved_data = saved_doc.to_dict()

    response_payload = {
        "message": "Player registered successfully.",
        "player": serialize_firestore_data(saved_data)
    }

    return https_fn.Response(
        json.dumps(response_payload),
        status=201,
        mimetype="application/json"
    )

@https_fn.on_request(cors=cors_opt)
def get_profile(req: https_fn.Request) -> https_fn.Response:
    """
    GET: Retrieves the full profile of a player by uid.
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)
        
    if req.method != "GET":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use GET."}),
            status=405,
            mimetype="application/json"
        )

    uid = req.args.get("uid")
    if not uid:
        return https_fn.Response(
            json.dumps({"error": "Missing required query parameter: uid"}),
            status=400,
            mimetype="application/json"
        )

    db_firestore = firestore.client()
    player_doc = db_firestore.collection("players").document(uid).get()

    if not player_doc.exists:
        return https_fn.Response(
            json.dumps({"error": "Player profile not found."}),
            status=404,
            mimetype="application/json"
        )

    return https_fn.Response(
        json.dumps(serialize_firestore_data(player_doc.to_dict())),
        status=200,
        mimetype="application/json"
    )

@https_fn.on_request(cors=cors_opt)
def update_avatar(req: https_fn.Request) -> https_fn.Response:
    """
    POST: Updates avatar fields for a player.
    Takes: uid, body, hair, outfit, accessory (each must be an integer 1-10)
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)
        
    if req.method != "POST":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use POST."}),
            status=405,
            mimetype="application/json"
        )

    try:
        body = req.get_json(silent=True)
    except Exception:
        body = None

    if not body:
        return https_fn.Response(
            json.dumps({"error": "Invalid or missing JSON request body."}),
            status=400,
            mimetype="application/json"
        )

    uid = body.get("uid")
    if not uid:
        return https_fn.Response(
            json.dumps({"error": "Missing required field: uid"}),
            status=400,
            mimetype="application/json"
        )

    avatar_fields = ["body", "hair", "outfit", "accessory"]
    avatar_updates = {}

    for field in avatar_fields:
        val = body.get(field)
        if val is None:
            return https_fn.Response(
                json.dumps({"error": f"Missing avatar field: {field}"}),
                status=400,
                mimetype="application/json"
            )
        
        # Check type (and avoid bool evaluating to int)
        if not isinstance(val, int) or isinstance(val, bool):
            return https_fn.Response(
                json.dumps({"error": f"Avatar field '{field}' must be an integer."}),
                status=400,
                mimetype="application/json"
            )

        if val < 1 or val > 10:
            return https_fn.Response(
                json.dumps({"error": f"Avatar field '{field}' must be in range 1-10."}),
                status=400,
                mimetype="application/json"
            )
        avatar_updates[field] = val

    db_firestore = firestore.client()
    player_ref = db_firestore.collection("players").document(uid)

    if not player_ref.get().exists:
        return https_fn.Response(
            json.dumps({"error": "Player profile not found."}),
            status=404,
            mimetype="application/json"
        )

    # Update nested avatar field
    player_ref.update({"avatar": avatar_updates})

    return https_fn.Response(
        json.dumps(avatar_updates),
        status=200,
        mimetype="application/json"
    )

@https_fn.on_request(cors=cors_opt)
def search_player(req: https_fn.Request) -> https_fn.Response:
    """
    GET: Performs a case-insensitive search by username query.
    Returns list of players matching the query (prefix search).
    Fields returned: uid, username, level, title, battle_record
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)
        
    if req.method != "GET":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use GET."}),
            status=405,
            mimetype="application/json"
        )

    username_query = req.args.get("username")
    if not username_query:
        return https_fn.Response(
            json.dumps({"error": "Missing required query parameter: username"}),
            status=400,
            mimetype="application/json"
        )

    query_str = username_query.strip().lower()
    if not query_str:
        return https_fn.Response(
            json.dumps({"error": "Username search query cannot be empty."}),
            status=400,
            mimetype="application/json"
        )

    db_firestore = firestore.client()
    players_ref = db_firestore.collection("players")

    # Prefix query: username >= query_str and username < query_str + '\uf8ff'
    docs = (
        players_ref
        .where("username", ">=", query_str)
        .where("username", "<", query_str + "\uf8ff")
        .limit(20)
        .get()
    )

    results = []
    for doc in docs:
        d = doc.to_dict()
        results.append({
            "uid": d.get("uid"),
            "username": d.get("username"),
            "level": d.get("level"),
            "title": d.get("title"),
            "battle_record": d.get("battle_record")
        })

    return https_fn.Response(
        json.dumps({"players": results}),
        status=200,
        mimetype="application/json"
    )

@https_fn.on_request(cors=cors_opt)
def add_xp(req: https_fn.Request) -> https_fn.Response:
    """
    POST: Adds XP to a player and handles level ups.
    Formula: xp_needed = ceil(100 * level^1.5)
    Multiple level-ups and job changes (levels divisible by 10) are handled.
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)

    if req.method != "POST":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use POST."}),
            status=405,
            mimetype="application/json"
        )

    try:
        body = req.get_json(silent=True)
    except Exception:
        body = None

    if not body:
        return https_fn.Response(
            json.dumps({"error": "Invalid or missing JSON request body."}),
            status=400,
            mimetype="application/json"
        )

    uid = body.get("uid")
    amount = body.get("amount")

    # Input validation
    if not uid or amount is None:
        return https_fn.Response(
            json.dumps({"error": "Missing required fields: uid, amount"}),
            status=400,
            mimetype="application/json"
        )

    if not isinstance(uid, str):
        return https_fn.Response(
            json.dumps({"error": "Field uid must be a string."}),
            status=400,
            mimetype="application/json"
        )

    if not isinstance(amount, int) or isinstance(amount, bool):
        return https_fn.Response(
            json.dumps({"error": "Field amount must be an integer."}),
            status=400,
            mimetype="application/json"
        )

    if amount < 0:
        return https_fn.Response(
            json.dumps({"error": "Field amount must be a non-negative integer."}),
            status=400,
            mimetype="application/json"
        )

    db_firestore = firestore.client()
    player_ref = db_firestore.collection("players").document(uid)
    player_snapshot = player_ref.get()

    if not player_snapshot.exists:
        return https_fn.Response(
            json.dumps({"error": "Player profile not found."}),
            status=404,
            mimetype="application/json"
        )

    player_data = player_snapshot.to_dict()
    level = player_data.get("level", 1)
    current_xp = player_data.get("current_xp", 0)
    stat_points = player_data.get("stat_points", 0)
    debuffs = player_data.get("debuffs", [])

    total_xp = current_xp + amount
    xp_needed = math.ceil(100 * (level ** 1.5))

    leveled_up = False
    job_change_triggered = False

    # Process level ups recursively/iteratively
    while total_xp >= xp_needed:
        level += 1
        total_xp -= xp_needed
        stat_points += 5
        leveled_up = True

        if level % 10 == 0:
            job_change_triggered = True
            if "job_change_pending" not in debuffs:
                debuffs.append("job_change_pending")

        # Recalculate for next level
        xp_needed = math.ceil(100 * (level ** 1.5))

    current_xp = total_xp

    # Update Firestore document
    player_ref.update({
        "level": level,
        "current_xp": current_xp,
        "stat_points": stat_points,
        "debuffs": debuffs
    })

    response_payload = {
        "new_level": level,
        "new_xp": current_xp,
        "xp_needed": xp_needed,
        "stat_points": stat_points,
        "leveled_up": leveled_up,
        "job_change_triggered": job_change_triggered
    }

    return https_fn.Response(
        json.dumps(response_payload),
        status=200,
        mimetype="application/json"
    )

# Type Advantage Rules mapping
TYPE_ADVANTAGE = {
    "Physics": "ICT",
    "Chemistry": "Biology",
    "Math": "Physics",
    "Biology": "English",
    "English": "Bangla",
    "Bangla": "Chemistry",
    "ICT": "Math"
}

@https_fn.on_request(cors=cors_opt)
def challenge_player(req: https_fn.Request) -> https_fn.Response:
    """
    POST: Challenges another player and creates a battle in RTDB.
    Takes: challenger_uid, opponent_uid
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)

    if req.method != "POST":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use POST."}),
            status=405,
            mimetype="application/json"
        )

    try:
        body = req.get_json(silent=True)
    except Exception:
        body = None

    if not body:
        return https_fn.Response(
            json.dumps({"error": "Invalid or missing JSON request body."}),
            status=400,
            mimetype="application/json"
        )

    challenger_uid = body.get("challenger_uid")
    opponent_uid = body.get("opponent_uid")

    if not challenger_uid or not opponent_uid:
        return https_fn.Response(
            json.dumps({"error": "Missing challenger_uid or opponent_uid."}),
            status=400,
            mimetype="application/json"
        )

    db_firestore = firestore.client()
    challenger_doc = db_firestore.collection("players").document(challenger_uid).get()
    opponent_doc = db_firestore.collection("players").document(opponent_uid).get()

    if not challenger_doc.exists or not opponent_doc.exists:
        return https_fn.Response(
            json.dumps({"error": "One or both players not found in Firestore."}),
            status=404,
            mimetype="application/json"
        )

    challenger_data = challenger_doc.to_dict()
    opponent_data = opponent_doc.to_dict()

    # Check debuffs for "shattered" or "job_change_pending"
    for player_name, data in [("Challenger", challenger_data), ("Opponent", opponent_data)]:
        debuffs = [d.lower() for d in data.get("debuffs", [])]
        if "shattered" in debuffs or "job_change_pending" in debuffs:
            return https_fn.Response(
                json.dumps({"error": f"{player_name} has active debuffs ('shattered' or 'job_change_pending') and cannot battle."}),
                status=400,
                mimetype="application/json"
            )

    # Construct battle state
    challenger_stats = challenger_data.get("stats", {"INT": 5, "VIT": 5, "AGI": 5, "PER": 5})
    opponent_stats = opponent_data.get("stats", {"INT": 5, "VIT": 5, "AGI": 5, "PER": 5})

    battle_id = db.reference("battles").push().key

    battle_data = {
        "battle_id": battle_id,
        "challenger": {
            "uid": challenger_uid,
            "username": challenger_data.get("username"),
            "level": challenger_data.get("level", 1),
            "stats": challenger_stats,
            "skills": challenger_data.get("skills", []),
            "title": challenger_data.get("title", "Beginner"),
            "character_type": challenger_data.get("character_type"),
            "hp": challenger_stats.get("VIT", 5) * 10,
            "max_hp": challenger_stats.get("VIT", 5) * 10,
            "mp": 5,
            "max_mp": 5,
            "debuffs": challenger_data.get("debuffs", []),
            "buffs": []
        },
        "opponent": {
            "uid": opponent_uid,
            "username": opponent_data.get("username"),
            "level": opponent_data.get("level", 1),
            "stats": opponent_stats,
            "skills": opponent_data.get("skills", []),
            "title": opponent_data.get("title", "Beginner"),
            "character_type": opponent_data.get("character_type"),
            "hp": opponent_stats.get("VIT", 5) * 10,
            "max_hp": opponent_stats.get("VIT", 5) * 10,
            "mp": 5,
            "max_mp": 5,
            "debuffs": opponent_data.get("debuffs", []),
            "buffs": []
        },
        "turn": challenger_uid,
        "status": "waiting",
        "winner": None,
        "battle_log": [],
        "created_at": int(time.time() * 1000)
    }

    db.reference(f"battles/{battle_id}").set(battle_data)

    return https_fn.Response(
        json.dumps({"battle_id": battle_id}),
        status=201,
        mimetype="application/json"
    )

@https_fn.on_request(cors=cors_opt)
def accept_battle(req: https_fn.Request) -> https_fn.Response:
    """
    POST: Opponent accepts a pending challenge.
    Takes: battle_id, opponent_uid
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)

    if req.method != "POST":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use POST."}),
            status=405,
            mimetype="application/json"
        )

    try:
        body = req.get_json(silent=True)
    except Exception:
        body = None

    if not body:
        return https_fn.Response(
            json.dumps({"error": "Invalid or missing JSON request body."}),
            status=400,
            mimetype="application/json"
        )

    battle_id = body.get("battle_id")
    opponent_uid = body.get("opponent_uid")

    if not battle_id or not opponent_uid:
        return https_fn.Response(
            json.dumps({"error": "Missing battle_id or opponent_uid."}),
            status=400,
            mimetype="application/json"
        )

    battle_ref = db.reference(f"battles/{battle_id}")
    battle = battle_ref.get()

    if not battle:
        return https_fn.Response(
            json.dumps({"error": "Battle not found."}),
            status=404,
            mimetype="application/json"
        )

    if battle.get("opponent", {}).get("uid") != opponent_uid:
        return https_fn.Response(
            json.dumps({"error": "Unauthorized opponent."}),
            status=400,
            mimetype="application/json"
        )

    if battle.get("status") != "waiting":
        return https_fn.Response(
            json.dumps({"error": "Battle is not in waiting status."}),
            status=400,
            mimetype="application/json"
        )

    battle_ref.update({"status": "active"})
    battle["status"] = "active"

    return https_fn.Response(
        json.dumps(battle),
        status=200,
        mimetype="application/json"
    )

@https_fn.on_request(cors=cors_opt)
def execute_turn(req: https_fn.Request) -> https_fn.Response:
    """
    POST: Executes a single turn (Attack, Skill, Flee).
    Takes: battle_id, uid, action, skill_name (optional), item_name (optional)
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)

    if req.method != "POST":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use POST."}),
            status=405,
            mimetype="application/json"
        )

    try:
        body = req.get_json(silent=True)
    except Exception:
        body = None

    if not body:
        return https_fn.Response(
            json.dumps({"error": "Invalid or missing JSON request body."}),
            status=400,
            mimetype="application/json"
        )

    battle_id = body.get("battle_id")
    uid = body.get("uid")
    action = body.get("action")
    skill_name = body.get("skill_name")
    item_name = body.get("item_name")

    if not battle_id or not uid or not action:
        return https_fn.Response(
            json.dumps({"error": "Missing battle_id, uid, or action."}),
            status=400,
            mimetype="application/json"
        )

    battle_ref = db.reference(f"battles/{battle_id}")
    battle = battle_ref.get()

    if not battle:
        return https_fn.Response(
            json.dumps({"error": "Battle not found."}),
            status=404,
            mimetype="application/json"
        )

    if battle.get("status") != "active":
        return https_fn.Response(
            json.dumps({"error": "Battle is not active."}),
            status=400,
            mimetype="application/json"
        )

    if battle.get("turn") != uid:
        return https_fn.Response(
            json.dumps({"error": "It is not your turn."}),
            status=400,
            mimetype="application/json"
        )

    # Resolve attacker and defender contexts
    if uid == battle["challenger"]["uid"]:
        attacker_key = "challenger"
        defender_key = "opponent"
    else:
        attacker_key = "opponent"
        defender_key = "challenger"

    attacker = battle[attacker_key]
    defender = battle[defender_key]

    result_log = ""
    damage_dealt = 0
    heal_amount = 0
    action_successful = True

    # ITEM Action (Not Implemented)
    if action == "item":
        return https_fn.Response(
            json.dumps({"message": "items coming soon"}),
            status=200,
            mimetype="application/json"
        )

    # FLEE Action
    elif action == "flee":
        battle["status"] = "finished"
        battle["winner"] = defender["uid"]
        
        # Win/loss updates
        db_firestore = firestore.client()
        challenger_ref = db_firestore.collection("players").document(battle["challenger"]["uid"])
        opponent_ref = db_firestore.collection("players").document(battle["opponent"]["uid"])

        if battle["winner"] == battle["challenger"]["uid"]:
            challenger_ref.update({"battle_record.wins": google_firestore.Increment(1)})
            opponent_ref.update({"battle_record.losses": google_firestore.Increment(1)})
        else:
            opponent_ref.update({"battle_record.wins": google_firestore.Increment(1)})
            challenger_ref.update({"battle_record.losses": google_firestore.Increment(1)})

        if "battle_log" not in battle or battle["battle_log"] is None:
            battle["battle_log"] = []
        battle["battle_log"].append({
            "actor": uid,
            "action": "flee",
            "result": f"{attacker['username']} fled! {defender['username']} wins the battle.",
            "timestamp": int(time.time() * 1000)
        })

        battle_ref.set(battle)
        return https_fn.Response(json.dumps(battle), status=200, mimetype="application/json")

    # ATTACK Action
    elif action == "attack":
        # Base damage = INT * 1.5
        base_dmg = attacker["stats"].get("INT", 5) * 1.5

        # Type advantage multiplier (1.5x)
        atk_type = attacker.get("character_type")
        def_type = defender.get("character_type")
        if atk_type and def_type and TYPE_ADVANTAGE.get(atk_type) == def_type:
            base_dmg *= 1.5
            result_log += "[Type Advantage!] "

        # WEAKENED debuff (-20% damage)
        is_weakened = any(d.lower() == "weakened" for d in attacker.get("debuffs", []))
        if is_weakened:
            base_dmg *= 0.8
            result_log += "[Weakened] "

        # BERSERKER Mode buff (+50% damage)
        is_berserker = any(b.lower() == "berserker_mode" for b in attacker.get("buffs", []))
        if is_berserker:
            base_dmg *= 1.5
            result_log += "[Berserker ATK Boost] "

        # Critical hit: 10% base + PER/100
        crit_chance = 0.10 + (attacker["stats"].get("PER", 5) / 100.0)
        is_crit = random.random() < crit_chance
        if is_crit:
            base_dmg *= 2.0
            result_log += "[CRITICAL HIT!] "

        # Defense calculation: Base DEF = VIT
        def_vit = defender["stats"].get("VIT", 5)
        # BERSERKER Mode reduces defender DEF by 30%
        def_berserker = any(b.lower() == "berserker_mode" for b in defender.get("buffs", []))
        if def_berserker:
            def_vit *= 0.7

        damage_dealt = max(1, int(base_dmg - def_vit))

        # Check Shield or Dodge buffs on defender
        if "shielded" in defender.get("buffs", []):
            damage_dealt = 0
            if defender["buffs"] is None: defender["buffs"] = []
            defender["buffs"] = [b for b in defender["buffs"] if b != "shielded"]
            result_log += f"{attacker['username']}'s attack was blocked by {defender['username']}'s shield!"
        elif "shadow_step" in defender.get("buffs", []):
            if defender["buffs"] is None: defender["buffs"] = []
            defender["buffs"] = [b for b in defender["buffs"] if b != "shadow_step"]
            if random.random() < 0.80:
                damage_dealt = 0
                result_log += f"{defender['username']} dodged the attack with Shadow Step!"
            else:
                defender["hp"] = max(0, defender["hp"] - damage_dealt)
                result_log += f"{attacker['username']} hit {defender['username']} for {damage_dealt} damage (Shadow Step dodge failed)."
        else:
            defender["hp"] = max(0, defender["hp"] - damage_dealt)
            result_log += f"{attacker['username']} hit {defender['username']} for {damage_dealt} damage."

    # SKILL Action
    elif action == "skill":
        if not skill_name:
            return https_fn.Response(
                json.dumps({"error": "Missing skill_name for skill action."}),
                status=400,
                mimetype="application/json"
            )

        # CURSED debuff reduces available skills by 1
        is_cursed = any(d.lower() == "cursed" for d in attacker.get("debuffs", []))
        skills_list = attacker.get("skills", [])
        if is_cursed:
            available_skills = skills_list[:-1] if len(skills_list) > 0 else []
        else:
            available_skills = skills_list

        if skill_name not in available_skills:
            return https_fn.Response(
                json.dumps({"error": f"Skill '{skill_name}' is locked, unavailable, or does not exist."}),
                status=400,
                mimetype="application/json"
            )

        # Define skill stats
        skills_config = {
            "Quantum Collapse": {"mp": 2},
            "Acid Nova": {"mp": 2},
            "Axiom Break": {"mp": 2},
            "Regen Field": {"mp": 2},
            "Mind Fracture": {"mp": 1},
            "Soul Verse": {"mp": 1},
            "System Override": {"mp": 3},
            "Shadow Step": {"mp": 1},
            "Berserker Mode": {"mp": 2},
            "Arise": {"mp": 3}
        }

        config = skills_config.get(skill_name)
        if not config:
            return https_fn.Response(
                json.dumps({"error": f"Skill config for '{skill_name}' is not defined."}),
                status=400,
                mimetype="application/json"
            )

        mp_cost = config["mp"]
        if attacker.get("mp", 0) < mp_cost:
            return https_fn.Response(
                json.dumps({"error": f"Not enough MP to cast {skill_name}. Needed: {mp_cost}"}),
                status=400,
                mimetype="application/json"
            )

        # Deduct MP
        attacker["mp"] -= mp_cost
        result_log += f"Used {skill_name} (Cost: {mp_cost} MP). "

        # Helper flags for damage calculations
        atk_int = attacker["stats"].get("INT", 5)
        is_weakened = any(d.lower() == "weakened" for d in attacker.get("debuffs", []))
        is_berserker = any(b.lower() == "berserker_mode" for b in attacker.get("buffs", []))
        def_vit = defender["stats"].get("VIT", 5)
        def_berserker = any(b.lower() == "berserker_mode" for b in defender.get("buffs", []))
        if def_berserker:
            def_vit *= 0.7

        # Skill logic executions
        if skill_name == "Quantum Collapse":
            base_dmg = atk_int * 3
            if is_weakened: base_dmg *= 0.8
            if is_berserker: base_dmg *= 1.5
            damage_dealt = max(1, int(base_dmg - def_vit))

        elif skill_name == "Acid Nova":
            base_dmg = atk_int * 2
            if is_weakened: base_dmg *= 0.8
            if is_berserker: base_dmg *= 1.5
            damage_dealt = max(1, int(base_dmg - def_vit))
            if defender.get("debuffs") is None: defender["debuffs"] = []
            if "burned" not in defender["debuffs"]:
                defender["debuffs"].append("burned")

        elif skill_name == "Axiom Break":
            base_dmg = atk_int * 2.5
            if is_weakened: base_dmg *= 0.8
            if is_berserker: base_dmg *= 1.5
            # Ignores 30% of defense
            ignored_def = def_vit * 0.7
            damage_dealt = max(1, int(base_dmg - ignored_def))

        elif skill_name == "Regen Field":
            heal_amount = atk_int * 2
            attacker["hp"] = min(attacker["max_hp"], attacker["hp"] + heal_amount)
            result_log += f"Healed self for {heal_amount} HP."

        elif skill_name == "Mind Fracture":
            if defender.get("debuffs") is None: defender["debuffs"] = []
            if "weakened" not in defender["debuffs"]:
                defender["debuffs"].append("weakened")
            result_log += f"Applied weakened debuff to {defender['username']}."

        elif skill_name == "Soul Verse":
            if attacker.get("buffs") is None: attacker["buffs"] = []
            if "shielded" not in attacker["buffs"]:
                attacker["buffs"].append("shielded")
            result_log += f"Applied shielded buff to self."

        elif skill_name == "System Override":
            if defender.get("debuffs") is None: defender["debuffs"] = []
            if "skip_turn" not in defender["debuffs"]:
                defender["debuffs"].append("skip_turn")
            result_log += f"Opponent will skip their next turn."

        elif skill_name == "Shadow Step":
            if attacker.get("buffs") is None: attacker["buffs"] = []
            if "shadow_step" not in attacker["buffs"]:
                attacker["buffs"].append("shadow_step")
            result_log += f"Applied shadow_step buff to self."

        elif skill_name == "Berserker Mode":
            if attacker.get("buffs") is None: attacker["buffs"] = []
            if "berserker_mode" not in attacker["buffs"]:
                attacker["buffs"].append("berserker_mode")
            result_log += f"Activated Berserker Mode (+50% ATK, -30% DEF)."

        elif skill_name == "Arise":
            if attacker.get("arise_used"):
                # Rollback MP deduction if check fails
                attacker["mp"] += mp_cost
                return https_fn.Response(
                    json.dumps({"error": "Arise can only be used once per battle."}),
                    status=400,
                    mimetype="application/json"
                )
            attacker["arise_used"] = True
            base_dmg = atk_int * 5
            if is_weakened: base_dmg *= 0.8
            if is_berserker: base_dmg *= 1.5
            damage_dealt = max(1, int(base_dmg - def_vit))

        # Apply damage for damaging skills
        if damage_dealt > 0:
            if "shielded" in defender.get("buffs", []):
                damage_dealt = 0
                if defender["buffs"] is None: defender["buffs"] = []
                defender["buffs"] = [b for b in defender["buffs"] if b != "shielded"]
                result_log += f"Skill damage was blocked by {defender['username']}'s shield!"
            elif "shadow_step" in defender.get("buffs", []):
                if defender["buffs"] is None: defender["buffs"] = []
                defender["buffs"] = [b for b in defender["buffs"] if b != "shadow_step"]
                if random.random() < 0.80:
                    damage_dealt = 0
                    result_log += f"Skill damage dodged with Shadow Step!"
                else:
                    defender["hp"] = max(0, defender["hp"] - damage_dealt)
                    result_log += f"Skill hit {defender['username']} for {damage_dealt} damage."
            else:
                defender["hp"] = max(0, defender["hp"] - damage_dealt)
                result_log += f"Dealt {damage_dealt} skill damage to {defender['username']}."

    else:
        return https_fn.Response(
            json.dumps({"error": "Invalid action. Supported actions: attack, skill, flee."}),
            status=400,
            mimetype="application/json"
        )

    # Post-Action resolution
    # Check HP conditions
    if defender["hp"] <= 0:
        battle["status"] = "finished"
        battle["winner"] = attacker["uid"]
        result_log += f" {defender['username']} has been defeated! {attacker['username']} wins!"

        # Update Firestore Player Records
        db_firestore = firestore.client()
        challenger_ref = db_firestore.collection("players").document(battle["challenger"]["uid"])
        opponent_ref = db_firestore.collection("players").document(battle["opponent"]["uid"])

        if battle["winner"] == battle["challenger"]["uid"]:
            challenger_ref.update({"battle_record.wins": google_firestore.Increment(1)})
            opponent_ref.update({"battle_record.losses": google_firestore.Increment(1)})
        else:
            opponent_ref.update({"battle_record.wins": google_firestore.Increment(1)})
            challenger_ref.update({"battle_record.losses": google_firestore.Increment(1)})

    # Switch Turn (if battle still active)
    if battle["status"] == "active":
        # Check if defender has "skip_turn" debuff
        defender_debuffs = defender.get("debuffs", [])
        if "skip_turn" in defender_debuffs:
            if defender["debuffs"] is None: defender["debuffs"] = []
            defender["debuffs"] = [d for d in defender["debuffs"] if d != "skip_turn"]
            result_log += f" {defender['username']}'s turn is skipped!"
            # Turn remains with attacker
        else:
            # Switch turn
            battle["turn"] = defender["uid"]

    # Save to battle logs
    if "battle_log" not in battle or battle["battle_log"] is None:
        battle["battle_log"] = []
    battle["battle_log"].append({
        "actor": uid,
        "action": action,
        "result": result_log,
        "timestamp": int(time.time() * 1000)
    })

    # Update RTDB
    battle_ref.set(battle)

    return https_fn.Response(
        json.dumps(battle),
        status=200,
        mimetype="application/json"
    )

@https_fn.on_request(cors=cors_opt)
def get_battle_state(req: https_fn.Request) -> https_fn.Response:
    """
    GET: Retrieves the current live state of a battle.
    Takes: battle_id
    """
    if req.method == "OPTIONS":
        return https_fn.Response(status=204)

    if req.method != "GET":
        return https_fn.Response(
            json.dumps({"error": "Method Not Allowed. Use GET."}),
            status=405,
            mimetype="application/json"
        )

    battle_id = req.args.get("battle_id")
    if not battle_id:
        return https_fn.Response(
            json.dumps({"error": "Missing required query parameter: battle_id"}),
            status=400,
            mimetype="application/json"
        )

    battle = db.reference(f"battles/{battle_id}").get()

    if not battle:
        return https_fn.Response(
            json.dumps({"error": "Battle not found."}),
            status=404,
            mimetype="application/json"
        )

    return https_fn.Response(
        json.dumps(battle),
        status=200,
        mimetype="application/json"
    )