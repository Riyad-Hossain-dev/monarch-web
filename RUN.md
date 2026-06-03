# Running and Testing the Monarch MMORPG Prototype

This repository contains the functional prototype and technical specification for 'Monarch', a 2D action MMORPG.

## 1. Prerequisites

- Python 3.12 or higher
- `pip` (Python package manager)

## 2. Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

## 3. Running the Backend

The backend is built with FastAPI. To start the local development server:

```bash
uvicorn app:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. You can explore the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.

## 4. Running the Frontend

The frontend is a Phaser.js game engine integrated with a modern UI layer.

Since it is a static HTML file, you can open it directly in your browser:

1.  Navigate to the `public/` directory.
2.  Open `game.html` in any modern web browser.

**Note:** The prototype is configured to trigger an automated "Exam" after 5 seconds of movement. You can use the **Arrow Keys** to move the character and click the UI buttons to answer questions.

## 5. Running Tests

To verify the backend logic and endpoint integrity, run the comprehensive test suite:

```bash
PYTHONPATH=. pytest test_main.py
```

This will run 24 unit tests covering user registration, player profiles, XP allocation, and the core Exam Trigger Engine.

## 6. Project Structure

- `main.py`: Core backend logic and FastAPI routes.
- `public/game.html`: Phaser.js frontend game engine and UI.
- `TECH_SPEC.md`: Detailed architecture blueprint and development roadmap.
- `exam_questions.json` & `item_directory.json`: Structured game data and schemas.
