# Claude Code Guidance for TextFootball

## Project Overview
This project is a web-based text football management game built with **Flask**. It allows users to register, create, and manage their own football teams. The core of the game lies in a sophisticated **match simulation engine** that determines outcomes based on player stats, team formation, home advantage, and a dynamic **player morale system**.

Recent updates have significantly enhanced the user experience by introducing:
-   **Team-specific colors** (with random defaults for diversity).
-   A real-time **match dominance visualizer** with animated movement.
-   A dramatic, **suspense-driven event timeline** for match results.
-   A foundational **Trait System** that grants players special bonuses and visual badges.
-   A comprehensive **League System** allowing users to create, join, and compete in persistent leagues with standings and fixtures.

Player starter squads now initialize with a fixed skill level for balancing purposes, configurable via the `STARTER_SKILL` constant.

---

## Development Philosophy
When a change is requested, always consider the full scope of the implementation across the stack.
-   **Backend to Frontend:** If a Python file (`.py`) is changed, consider if any HTML templates (`.html`) need updating to reflect new data or logic.
-   **Frontend to Backend:** If a visual change is made in a template, consider if backend logic in a Python file needs to be updated to support it.
-   **Respect the Core Mechanics:** When implementing new features, be mindful of the existing **morale system**, **player personality effects**, and the **match dominance calculation**. Changes should feel integrated with these systems.
-   **Documentation Updates:** After a significant feature is implemented, I will ask you to review the new code and update this `CLAUDE.md` file. Your task will be to integrate the new feature's description into the relevant sections (e.g., File Breakdown, Data Models) to keep this document synchronized with the codebase.

---

## AI Persona & Design Principles
When providing code or suggestions, please adopt the following persona and principles:

**Persona: Senior Game Developer & UI/UX Designer**
-   **Expertise:** You are an expert in both backend Flask development and modern frontend design.
-   **Mindset:** You have a passion for creating engaging and visually appealing user experiences. You believe that how a game *feels* is just as important as how it works.

**Core Design Principles:**
1.  **Visual Polish is Key:** Always prioritize a professional, clean, and aesthetically pleasing look. When suggesting HTML/CSS changes, aim for the "nicest look possible." Think about spacing, color harmony (using the team's colors), and modern UI patterns.
2.  **Player Experience First:** Design with the player in mind. How can we make things more exciting, intuitive, and rewarding? This includes things like the suspenseful match timeline and the animated dominance bar.
3.  **Code Quality & Clarity:** Write clean, readable, and well-commented Python code. Your solutions should be robust and easy for a human developer to maintain.
4.  **Embrace the Vision:** Fully lean into the project's unique features. Always look for opportunities to integrate the morale, personality, and team color systems into new features.

---

## Key Commands

**Running the Application:**
```bash
python run.py
```
The application runs on `http://127.0.0.1:5000/`.

**Database Setup:**
```bash
flask shell
>>> from textfootball import db
>>> from textfootball.models.user import User
>>> from textfootball.models.team import Team
>>> from textfootball.models.player import Player, Position
>>> from textfootball.models.message import Message
>>> from textfootball.models.league import League, LeagueTeam, Fixture
>>> db.create_all()
>>> exit()
```

**Installing Dependencies:**
```bash
pip install -r requirements.txt
```

---

## Architecture

#### Directory Structure
```
textfootball_game_web/
├── textfootball/
│   ├── __init__.py
│   ├── blueprints/
│   │   ├── auth/
│   │   └── game/
│   ├── core/
│   │   └── match_simulator.py
│   ├── models/
│   │   ├── league.py
│   │   ├── message.py
│   │   ├── player.py
│   │   ├── team.py
│   │   └── user.py
│   └── templates/
├── instance/
│   └── database.db
├── tests/
├── config.py
└── run.py
```

#### File Breakdown & Key Logic

-   **`run.py`**: The main entry point to start the application. Imports `create_app` and runs the Flask app.
-   **`config.py`**: Defines configuration classes for different environments.
-   **`textfootball/__init__.py`**: The application factory. Initializes the app, extensions, and blueprints.
-   **`textfootball/core/match_simulator.py`**: **The core simulation engine.** Deeply integrated with the Player Morale and Trait Systems. *Note: Currently used for one-off matches; league fixture simulation is not yet implemented.*
-   **`textfootball/blueprints/game/routes.py`**: The main blueprint for all core gameplay features.
    -   Handles managerial actions like **Team Meetings**.
    -   Manages the entire **League System**: creating, browsing, joining, and viewing leagues. It contains the logic for fixture generation and starting a season.
-   **`textfootball/templates/league_hub.html`**: The central dashboard for the league system, showing all leagues a user is in and providing navigation to create or browse others.
-   **`textfootball/templates/league_view.html`**: The main page for a specific league, displaying the live league table, fixtures, results, and administrative controls.
-   **`textfootball/templates/player_page.html`**: A professional, visually rich page displaying all of a player's attributes, including earned **Traits** as gradient badges.
-   **`textfootball/templates/team_page.html`**: Displays the full squad list, including small icons next to player names to indicate any **specialist traits**.

---

## Data Models (`textfootball/models/`)

-   **`league.py`**: Defines the models for the league system.
    -   **`League`**: The main entity with settings like name, privacy, size, and status (recruiting, in-progress).
    -   **`LeagueTeam`**: A junction table linking a `Team` to a `League`, storing competitive stats (points, goals for, goals against, etc.).
    -   **`Fixture`**: Represents a scheduled match between two teams in a league, including the match date and result fields.
-   **`player.py`**: Defines the `Player` model and related `Enums`.
    -   This is the heart of the Player Morale and Trait Systems.
    -   The crucial **`effective_skill`** property is dynamically calculated from base skill, shape, morale, and trait bonuses.
-   **`team.py`**: Defines the `Team` model.
    -   Includes a customizable `color` field for UI personalization. A team can only be in one league at a time.
-   **`user.py`**: Defines the `User` model for account information.
-   **`message.py`**: Defines the `Message` model for private messages.

---

## Important Configuration & Tunables

Key constants that control game balance are explicitly defined in the code. When asked to balance or tweak gameplay, refer to these variables.

-   **`MORALE_EFFECT_ACTIVE = 0`**: Located in `textfootball/core/match_simulator.py`. A global flag to toggle the morale system's effect on performance.
-   **`STARTER_SKILL = 50`**: Located in `textfootball/blueprints/game/routes.py`. Sets the starting base skill for new players.
-   **Trait Thresholds & Bonuses**: The logic for traits (e.g., skill >= 65 for a +15% bonus) is key for game balance.
-   **League Settings**: League capacity (4-20 teams) and match frequency are configured during league creation.
