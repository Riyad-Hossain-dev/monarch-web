# Monarch: Action MMORPG Technical Specification & Development Blueprint

## Phase 1: Architecture & Tech Stack Integration

### Frontend: HTML5 Canvas & Modern UI
- **Engine:** Phaser.js (v3.x) for 2D tilemap rendering, player movement, and real-time sprite syncing.
- **Tilemaps:** Tiled Editor (.json exports) using GBA-style assets (16x16 tiles).
- **UI Layer:** React.js or Vue.js overlaid on the Phaser canvas for HUD (HP/MP bars), Inventory modals, and the Exam interface.
- **State Management:** Redux or Pinia for local player state syncing between the UI and Game Engine.

### Backend: Real-Time Node.js Microservices
- **Server:** Node.js with Express.
- **Real-Time:** Socket.io for bidirectional communication (X, Y coordinates, chat, global events).
- **Instance Management:** Room-based logic to handle different dungeon instances and maps.

### Database: Hybrid Schema Design
- **Primary DB:** PostgreSQL (for relational Player Profiles, Items, and Stats) or MongoDB (for flexible Game Data).
- **Caching:** Redis for volatile session data (active player positions, current lobby state).

---

## Phase 2: Core Gameplay & State Machine Logic

### The 'Exam Trigger Engine'
1.  **Threshold Detection:** The Backend monitors Player XP. When `XP >= Threshold` OR `TriggerZone == DungeonBossRoom`:
2.  **Lockdown Event:**
    -   Backend emits `EXAM_TRIGGERED` to the specific Socket.
    -   Player `isLocked` flag set to `true` in DB/Redis.
    -   Frontend freezes character movement and disables skill inputs.
3.  **Exam Modal:**
    -   A responsive modal (Stitch AI design) slides over the Canvas.
    -   Timer starts (e.g., 60 seconds).
4.  **Submission & Verification:**
    -   Answers sent to `/verify-exam` endpoint.
    -   On success: Unlock character evolution, grant `Shadow Monarch` class, or drop S-Rank loot.
    -   On failure: Player is expelled from the dungeon; debuff `Shattered` applied (-20% stats).

### Scoring & Reward Calculator
- **Correctness Multiplier:** `BaseXP * (CorrectAnswers / TotalQuestions)`
- **Speed Bonus:** `TimeRemaining / TotalTime * BonusFactor`
- **Stat Allocation:** Correct answers in specific categories (Math, Logic, Lore) map to STR, INT, and AGI respectively.

---

## Phase 3: Real-Time Multiplayer & PvP Specification

### Socket.io Architecture
- `player_move`: Broadcasts `(x, y, flipX, animationState)` to all users in the same room.
- `room_sync`: Periodic heartbeat to ensure all clients have the same monster/item locations.

### PvP Duel Request System
1.  **Interaction:** Player A clicks Player B -> `INIT_DUEL_REQUEST`.
2.  **Handshake:** Player B receives a toast; if accepted -> `DUEL_START`.
3.  **Instancing:** Both players are moved to a temporary "Virtual Arena" coordinate space or local instance.
4.  **Turn-Based or Real-Time Combat:**
    -   **Real-Time:** Uses an authoritative server to calculate hitboxes and latency compensation.
    -   **State Sync:** Server validates each attack animation vs defender position.

---

## Phase 4: Database Schemas & Data Seeding

### Player Profile (SQL/NoSQL)
```json
{
  "uid": "string",
  "username": "string",
  "class": "Shadow Monarch (Tier 2)",
  "stats": { "STR": 15, "AGI": 20, "INT": 45 },
  "inventory": [
    {"id": "item_001", "rank": "S", "type": "Weapon", "name": "Kamish's Wrath"}
  ],
  "position": { "map": "ant_tunnel", "x": 1024, "y": 768 }
}
```

### Exam Question Bank
```json
{
  "category": "Ancient Runes (Logic)",
  "difficulty": "Rank-S",
  "questions": [
    {
      "id": "q_101",
      "text": "Solve the sequence: 2, 4, 8, 16, ?",
      "options": ["32", "64", "24", "48"],
      "answer": "32",
      "reward_multiplier": 2.5
    }
  ]
}
```

---

## Phase 5: Step-by-Step Development Roadmap

1.  **Phase 1 (Week 1-2):** Setup Phaser boilerplate + Sprite movement + Socket.io "Hello World" (seeing other circles move).
2.  **Phase 2 (Week 3):** Implement Tiled map loading and collision detection. Setup Express API for Player registration.
3.  **Phase 3 (Week 4):** Build the **Exam Modal UI**. Logic for freezing player movement and fetching random questions.
4.  **Phase 4 (Week 5):** Inventory system & Stat allocation UI. Database persistence for items.
5.  **Phase 5 (Week 6):** PvP Arena implementation and Dungeon Boss logic. Full Beta Testing on a free tier (Railway/Render + MongoDB Atlas).
