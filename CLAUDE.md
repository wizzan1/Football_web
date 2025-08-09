CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project Overview
This is a web-based football management simulation game built with Flask. Users can create and manage football teams, simulate matches, and track player statistics with a comprehensive morale and personality system.

Development Philosophy
When a change is requested, always consider the full scope of the implementation across the stack:

If a backend change is made in a Python (.py) file, consider if any corresponding changes are needed in the HTML templates (.html) to reflect the new logic or data.

If a visual or frontend change is requested in an HTML template, consider if any backend logic in the Python (.py) files needs to be updated to support it.

Development Commands
Running the Application
Bash

python run.py
The application runs on http://127.0.0.1:5000/

Database Setup
To create a new database:

Bash

flask shell
from textfootball import db
from textfootball.models.user import User
from textfootball.models.team import Team
from textfootball.models.player import Player, Position
from textfootball.models.message import Message
db.create_all()
exit()
Installing Dependencies
Bash

pip install -r requirements.txt
Architecture
Flask Application Factory Pattern
run.py - Entry point that creates the app using create_app() factory

textfootball/__init__.py - Contains the application factory function and database initialization

config.py - Configuration classes for different environments (Development, Testing)

Blueprint Structure
textfootball/blueprints/auth/ - Authentication routes (login, register)

textfootball/blueprints/game/ - Main game functionality routes

Core Game Engine
textfootball/core/match_simulator.py - The heart of the game simulation
  - Contains MatchSimulator class for match logic
  - Implements detailed football mechanics (shots, penalties, free kicks)
  - Features advanced morale system with personality-based reactions
  - Supports both regular matches and knockout matches with penalty shootouts

Data Models
Located in textfootball/models/:

user.py - User authentication and management

team.py - Team model with color theming and morale tracking

player.py - Player model with position enum, personality system, and skill calculations

message.py - In-game messaging system

Key Game Features
Player System
Positions: Goalkeeper, Defender, Midfielder, Forward

Skills: Base skill, shape (fitness), effective skill calculation

Specialties: Free kick ability, penalty taking/saving

Morale System: 0-100 scale affecting player performance

Personalities: Professional, Ambitious, Stoic, Volatile (affects morale reactions)

Match Simulation
Realistic match flow with midfield battles, attacks, and defensive actions

Shot distance affects goal probability (optimal distance: 12m)

Home advantage boost (3% multiplier)

Free kicks and penalty kicks with specialized mechanics

Detailed logging system for match events

Dominance calculation based on possession, territory, and actions

Morale System
Post-match morale updates based on results and individual performance

Personality-based reaction multipliers

Goal bonuses and hat-trick bonuses

Morale drift towards target value for non-playing players

Currently disabled via MORALE_EFFECT_ACTIVE = 0 flag for balancing

Configuration Tunables
The match simulator includes extensive configuration variables at the top of match_simulator.py:

Formation setup, home advantage factors

Shot mechanics, goalkeeper scaling

Free kick and penalty parameters

Morale system multipliers

Database
SQLite database with Flask-SQLAlchemy ORM

Database file located at instance/database.db

Supports cascade deletions for team-player relationships

Frontend
Bootstrap 5 responsive UI

Jinja2 templating with custom filters (nl2br)

Team color theming system

Match result visualization with event timeline

Development Notes
Team Colors
Teams have customizable hex color codes (color field) used throughout the UI for theming.

Session Management
The app uses Flask sessions to track the currently selected team (selected_team_id), making it available in all templates via context processor.

Testing Configuration
The TestingConfig class uses in-memory SQLite database and disables CSRF for automated testing convenience.

Match Simulation Balance
Current morale system is disabled for balancing (MORALE_EFFECT_ACTIVE = 0)

Shape is set to 100% for all players during balancing phase

Extensive tuning parameters available for gameplay adjustment