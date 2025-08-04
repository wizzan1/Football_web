import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Get the absolute path of the directory where this file is located
basedir = os.path.abspath(os.path.dirname(__file__))

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    # --- Configuration ---
    app.config['SECRET_KEY'] = 'a_very_secret_key_for_development'
    # Set the database path to be inside our 'app' folder
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')

    db.init_app(app)

    # Import and register the blueprints
    from .routes_auth import auth_bp
    from .routes_game import game_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(game_bp)

    return app
