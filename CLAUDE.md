# Claude Code Guidance for TextFootball

## Project Overview
This project is a web-based text football management game built with **Flask**. It allows users to register, create, and manage their own football teams. The core of the game lies in a sophisticated **match simulation engine** that determines outcomes based on player stats, team formation, home advantage, and a dynamic **player morale system**.

Recent updates have significantly enhanced the user experience by introducing:
-   **Team-specific colors** (with random defaults for diversity).
-   A real-time **match dominance visualizer** with animated movement for excitement.
-   A more dramatic, **suspense-driven event timeline** for match results featuring colored storytelling and icons for professional appeal.

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
-   **`config.py`**: Defines configuration classes for different environments (`DevelopmentConfig`, `TestingConfig`). `TestingConfig` uses an in-memory SQLite database.
-   **`instance/database.db`**: The SQLite database file, kept out of version control.
-   **`textfootball/__init__.py`**: The application factory. This file contains the `create_app()` function which:
    -   Initializes the Flask application and loads configuration.
    -   Initializes extensions like SQLAlchemy (`db`).
    -   Imports and registers all blueprints.
    -   Contains application-wide logic like context processors (e.g., for injecting the current team into templates) and custom Jinja filters.
-   **`textfootball/core/match_simulator.py`**: **The core simulation engine for the entire game.**
    -   The engine is event-driven and deeply integrated with the Player Morale System.
    -   It features a **Dominance System** that calculates real-time match control based on possession, territory, and key actions.
    -   Shot outcome logic is **distance-dependent**, making tactical positioning crucial.
    -   It generates multi-stage event logs with HTML for colored storytelling, creating suspenseful **Shot Buildup Sequences** with pre-shot announcements before revealing the outcome.
    -   After each match, it calculates nuanced **morale updates** for every player based on result, performance, and personality. This is conditionally disabled via `MORALE_EFFECT_ACTIVE=0`.
    -   It contains modes for both detailed single-match simulation (which saves morale changes) and high-speed Monte Carlo analysis (which does not).
-   **`textfootball/blueprints/game/routes.py`**: The main blueprint for all core gameplay features.
    -   It is the hub for managerial agency, featuring a **Team Meeting system** where managers can Praise, Encourage, or Criticize their squad to directly impact player morale.
    -   Starter squads are generated with diverse personalities, but with fixed `free_kick_ability=50` and `skill=50` (via `STARTER_SKILL` constant) for balancing.
    -   Team creation assigns random colors if not specified for visual diversity.
-   **`textfootball/templates/match_result.html`**: Provides a rich, dynamic visualization of match outcomes.
    -   Features a live-scrolling event timeline that builds suspense through a **Shot Buildup Sequence**.
    -   A real-time **Dominance Bar** visually represents the flow of the match, shifting between team colors with an animated indicator.
-   **`textfootball/templates/simulate.html`**: The pre-match analysis page that uses team-specific colors in its probability charts and statistical tables.
-   **`textfootball/templates/player_page.html`**: A professional, visually rich page displaying all of a player's attributes.
    -   **Header Design:** Features a team color gradient background, a large shirt number watermark, and icon-based badges for position, number, and age.
    -   **Complete Attribute Display:** Uses a two-column card layout to show everything: core stats (Skill, Potential, Shape) with color-coded progress bars, the calculated `Effective Skill`, mental attributes (Morale with emoji indicators, Personality with descriptions), and special skills (Free Kicks, Penalties).

---

## Data Models (`textfootball/models/`)

-   **`player.py`**: Defines the `Player` model and related `Enums` (`Position`, `Personality`).
    -   This is the heart of the Player Morale System, defining personality (`Stoic`, `Volatile`, etc.) and morale level.
    -   The crucial **`effective_skill`** property is dynamically calculated based on a player's base `skill`, current `shape`, and current `morale` (conditionally via `MORALE_EFFECT_ACTIVE=1`), making team psychology a key factor in performance.
-   **`team.py`**: Defines the `Team` model.
    -   Includes a customizable `color` field (hex code) for UI personalization.
    -   Includes properties for calculating average squad morale (`average_morale`).
    -   Includes a field (`last_meeting_date`) to manage the cooldown for team meetings.
-   **`user.py`**: Defines the `User` model for account information.
-   **`message.py`**: Defines the `Message` model for private messages.

---

## Important Configuration & Tunables

Key constants that control game balance are explicitly defined in the code. When asked to balance or tweak gameplay, refer to these variables.

-   **`MORALE_EFFECT_ACTIVE = 0`**: Located in `textfootball/core/match_simulator.py`. This is a global flag to disable (0) or enable (1) the morale system's effect on player performance during matches. It is **currently OFF for balancing**.
-   **`STARTER_SKILL = 50`**: Located in `textfootball/blueprints/game/routes.py`. This sets the starting base `skill` for all newly generated players in a starter squad.
-   **Other Tunables**: The top of `match_simulator.py` contains many other constants for formation setup, home advantage, shot mechanics, goalkeeper scaling, free kicks, and penalties.
