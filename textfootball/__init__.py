# C:\...\my_football_game\HTML\app\__init__.py (Updated)

from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup

# db is initialized here, but not attached to an app
db = SQLAlchemy()

# The factory now accepts a 'config_class' argument
def create_app(config_class):
    app = Flask(__name__)

    # --- Configuration ---
    # This ONE line replaces the hardcoded configs.
    # It loads all settings from the config object we pass in from run.py.
    app.config.from_object(config_class)

    # Initialize the database with our app
    db.init_app(app)

    # Import and register the blueprints (this part remains the same)
    from .blueprints.auth.routes import auth_bp
    from .blueprints.game.routes import game_bp
    from .blueprints.league.routes import league_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(game_bp)
    app.register_blueprint(league_bp)

    # Context processor to inject selected_team and user_teams into all templates
    @app.context_processor
    def inject_selected_team():
        from .models.team import Team
        from .models.user import User  # Import here to avoid circular dependencies
        
        user_teams = []
        selected_team = None
        
        if 'username' in session:
            user = User.query.filter_by(username=session['username']).first()
            if user:
                user_teams = user.teams
                
        if 'selected_team_id' in session:
            selected_team = Team.query.get(session['selected_team_id'])
            # Verify the team still exists and belongs to the user
            if selected_team and 'username' in session:
                user = User.query.filter_by(username=session['username']).first()
                if user and selected_team.user_id != user.id:
                    selected_team = None
                    session.pop('selected_team_id', None)
                    
        return dict(selected_team=selected_team, user_teams=user_teams)

    # Custom Jinja filter for nl2br
    # This is UNCHANGED
    def nl2br(value):
        result = value.replace('\n', '<br>\n')
        return Markup(result)

    app.jinja_env.filters['nl2br'] = nl2br

    return app
