# textfootball/models/team.py

from textfootball import db
# NEW: Import datetime
from datetime import datetime

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    country = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    players = db.relationship('Player', backref='team', lazy=True, cascade="all, delete-orphan")
    league = db.Column(db.String(100), nullable=True, default=None)
    division = db.Column(db.String(50), nullable=True, default=None)
    season = db.Column(db.Integer, nullable=True, default=None)

    # NEW: Morale System - Interaction Cooldown
    # The 'why': Prevents the manager from spamming team meetings.
    last_meeting_date = db.Column(db.DateTime, nullable=True, default=None)

    @property
    def average_morale(self):
        """ Calculates the current average morale of the squad. """
        if not self.players:
            return 75 # Default baseline if no players exist
        return sum(player.morale for player in self.players) / len(self.players)

    def get_morale_description(self):
        """ Returns a qualitative description of the team's mental state. """
        avg = self.average_morale
        if avg >= 95:
            return "Ecstatic"
        elif avg >= 85:
            return "Confident"
        elif avg >= 75:
            return "Good"
        elif avg >= 60:
            return "Stable"
        elif avg >= 45:
            return "Low"
        elif avg >= 30:
            return "Very Low"
        else:
            return "Crisis"
