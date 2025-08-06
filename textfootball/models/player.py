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
    
    # NEW: Penalty attributes as per requirements
    penalty_taking = db.Column(db.Integer, nullable=False, default=50)
    penalty_saving = db.Column(db.Integer, nullable=False, default=50)
    
    potential = db.Column(db.Integer, nullable=False)
    shape = db.Column(db.Integer, nullable=False)
    shirt_number = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)

    @property
    def effective_skill(self):
        """ General on-pitch effectiveness, influenced heavily by shape. """
        # The 'why': A player's physical and mental sharpness (shape) has a large impact on general play.
        shape_multiplier = 0.3 + (self.shape * 0.7 / 100.0)
        return self.skill * shape_multiplier

    @property
    def effective_fk_ability(self):
        """ Free kick ability, moderately influenced by shape (composure, focus). """
        # The 'why': Shape has a lesser, but still important, impact on set-piece specialty.
        shape_multiplier = 0.5 + (self.shape * 0.5 / 100.0)
        return self.free_kick_ability * shape_multiplier

    # NEW: Effective penalty properties as per requirements
    @property
    def effective_penalty_taking(self):
        """ Penalty taking ability, moderately influenced by shape (composure, focus). """
        # The 'why': Similar to free kicks, composure and focus (shape) are key for penalties.
        shape_multiplier = 0.5 + (self.shape * 0.5 / 100.0)
        return self.penalty_taking * shape_multiplier

    @property
    def effective_penalty_saving(self):
        """ Goalkeeper's penalty saving ability, moderately influenced by shape. """
        # The 'why': A keeper's sharpness and reflexes (shape) are critical in a penalty situation.
        shape_multiplier = 0.5 + (self.shape * 0.5 / 100.0)
        return self.penalty_saving * shape_multiplier
