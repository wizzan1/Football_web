# app/models.py (unchanged, provided for completeness but no modifications needed)
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import enum

class Position(enum.Enum):
    GOALKEEPER = "Goalkeeper"
    DEFENDER = "Defender"
    MIDFIELDER = "Midfielder"
    FORWARD = "Forward"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    # MODIFIED: A user can now have a list of teams. Renamed 'team' to 'teams'.
    teams = db.relationship('Team', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    country = db.Column(db.String(50), nullable=False)
    # This line must NOT have unique=True
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    players = db.relationship('Player', backref='team', lazy=True, cascade="all, delete-orphan")

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Enum(Position), nullable=False)
    skill = db.Column(db.Integer, nullable=False)
    potential = db.Column(db.Integer, nullable=False) # "UV" (utvecklingsvärde)
    shape = db.Column(db.Integer, nullable=False)
    shirt_number = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
