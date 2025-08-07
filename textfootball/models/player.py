# textfootball/models/player.py

from textfootball import db
import enum
import math

# The Position enum belongs here with the Player model
class Position(enum.Enum):
    GOALKEEPER = "Goalkeeper"
    DEFENDER = "Defender"
    MIDFIELDER = "Midfielder"
    FORWARD = "Forward"

# NEW: Personality Enum
# The 'why': Players shouldn't react uniformly to events. Personality adds depth,
# making some players resilient to losses (Stoic) and others highly motivated by wins (Ambitious).
# This influences how much their morale shifts after matches or interactions.
class Personality(enum.Enum):
    PROFESSIONAL = "Professional" # Baseline, predictable reactions.
    AMBITIOUS = "Ambitious"       # Larger positive swings, moderate negative swings.
    STOIC = "Stoic"               # Smaller swings in both directions. Resilient.
    VOLATILE = "Volatile"         # Large swings in both directions. High risk/reward.

# NEW: Temporary flag to disable morale effects for balancing purposes.
# Set to 0 to ignore morale in effective_skill calculations.
# Change to 1 to enable morale impact.
MORALE_EFFECT_ACTIVE = 0

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Enum(Position), nullable=False)
    skill = db.Column(db.Integer, nullable=False)
    free_kick_ability = db.Column(db.Integer, nullable=False, default=50)

    penalty_taking = db.Column(db.Integer, nullable=False, default=50)
    penalty_saving = db.Column(db.Integer, nullable=False, default=50)

    potential = db.Column(db.Integer, nullable=False)
    shape = db.Column(db.Integer, nullable=False)
    shirt_number = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)

    # NEW: Morale System Attributes
    # Morale (0-100). Defaulting to 80 (Good).
    morale = db.Column(db.Integer, nullable=False, default=80)
    # Personality trait influencing morale changes.
    personality = db.Column(db.Enum(Personality), nullable=False, default=Personality.PROFESSIONAL)

    # --- Morale System Configuration ---

    # The maximum boost/penalty applied to effective_skill due to morale.
    # A 10% swing means a player can perform 10% better or worse than their shape dictates.
    MORALE_IMPACT_FACTOR = 0.10

    # Requirement: 100 should be neutral (1.0x multiplier).
    MORALE_NEUTRAL_POINT = 100

    @property
    def effective_skill(self):
        """ General on-pitch effectiveness, influenced by shape AND morale. """
        # 1. Calculate base effectiveness from shape.
        shape_multiplier = 0.3 + (self.shape * 0.7 / 100.0)
        base_effectiveness = self.skill * shape_multiplier

        # 2. Calculate the morale multiplier.
        # If 100 is neutral (1.0x), we only apply penalties for morale < 100.

        if MORALE_EFFECT_ACTIVE == 1:
            if self.morale >= 100:
                morale_multiplier = 1.0
            else:
                # Calculate the penalty. If Morale=0, penalty is max (e.g., -10%). If Morale=100, penalty is 0%.
                # Penalty = (100 - Morale) / 100 * MAX_PENALTY
                penalty = ((100 - self.morale) / 100.0) * self.MORALE_IMPACT_FACTOR
                morale_multiplier = 1.0 - penalty

                # Example: Morale 50. Penalty = (100-50)/100 * 0.10 = 0.05. Multiplier = 0.95.
        else:
            morale_multiplier = 1.0  # Morale effect disabled for balancing

        return base_effectiveness * morale_multiplier

    @property
    def effective_fk_ability(self):
        """ Free kick ability, moderately influenced by shape (composure, focus). """
        shape_multiplier = 0.5 + (self.shape * 0.5 / 100.0)
        # Note: We are intentionally NOT applying morale to specialty skills (FK/Penalties) for now.
        # Composure is already modeled by 'shape'.
        return self.free_kick_ability * shape_multiplier

    @property
    def effective_penalty_taking(self):
        """ Penalty taking ability, moderately influenced by shape (composure, focus). """
        shape_multiplier = 0.5 + (self.shape * 0.5 / 100.0)
        return self.penalty_taking * shape_multiplier

    @property
    def effective_penalty_saving(self):
        """ Goalkeeper's penalty saving ability, moderately influenced by shape. """
        shape_multiplier = 0.5 + (self.shape * 0.5 / 100.0)
        return self.penalty_saving * shape_multiplier

    def get_personality_multiplier(self, is_positive_event):
        """ Returns the morale adjustment multiplier based on personality. """
        if self.personality == Personality.PROFESSIONAL:
            return 1.0
        elif self.personality == Personality.AMBITIOUS:
            # Ambitious players love wins, but are slightly resilient to losses.
            return 1.5 if is_positive_event else 0.8
        elif self.personality == Personality.STOIC:
            # Stoic players are unmoved by most events.
            return 0.6
        elif self.personality == Personality.VOLATILE:
            # Volatile players swing hard in both directions.
            return 1.8
        return 1.0
