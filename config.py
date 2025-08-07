## C:\Users\tobia\Desktop\Vampire Game\my_football_game\HTML\config.py

import os

# This line automatically determines the absolute path to your project's root folder.
# This makes your configuration portable to other computers.
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration class. Contains settings common to all environments."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-secret-key-you-should-change'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Add any other global settings here

class DevelopmentConfig(Config):
    """Configuration for development."""
    DEBUG = True

    # This is the crucial line that connects to your database in its new location.
    # It builds the path: 'sqlite:///C:\...\my_football_game\HTML\instance\database.db'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')

class TestingConfig(Config):
    """Configuration for running automated tests."""
    TESTING = True
    # For tests, it's best practice to use a separate, temporary database.
    # An in-memory SQLite database is perfect for this.
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False # Disable security forms during tests for convenience.
