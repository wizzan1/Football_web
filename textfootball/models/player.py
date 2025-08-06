# textfootball/models/player.py

from textfootball import db
import enum

# The Position enum belongs here with the Player model
class Position(enum.Enum):
    GOALKEEPER = "Goalkeeper"
    DEFENDER = "Defender"
    MIDFIELDER = "Midfielder"
    FORWARD = "Forward"

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Enum(Position), nullable=False)
    skill = db.Column(db.Integer, nullable=False)
    free_kick_ability = db.Column(db.Integer, nullable=False, default=50)
    potential = db.Column(db.Integer, nullable=False)
    shape = db.Column(db.Integer, nullable=False)
    shirt_number = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)

    @property
    def effective_skill(self):
        shape_multiplier = 0.3 + (self.shape * 0.7 / 100.0)
        return self.skill * shape_multiplier

    @property
    def effective_fk_ability(self):
        shape_multiplier = 0.5 + (self.shape * 0.5 / 100.0)
        return self.free_kick_ability * shape_multiplier
