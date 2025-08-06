# textfootball/models/team.py

from textfootball import db

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    country = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    players = db.relationship('Player', backref='team', lazy=True, cascade="all, delete-orphan")
    league = db.Column(db.String(100), nullable=True, default=None)
    division = db.Column(db.String(50), nullable=True, default=None)
    season = db.Column(db.Integer, nullable=True, default=None)
