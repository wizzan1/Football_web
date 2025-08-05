# app/match_sim.py (complete file with fixes for no goals and safeguards)
import random
import math
from app import db
from .models import Team, Player, Position

# Configuration Constants
FORMATION = {
    Position.GOALKEEPER: 1,
    Position.DEFENDER: 4,
    Position.MIDFIELDER: 4,
    Position.FORWARD: 2
}

HOME_ADVANTAGE_BOOST = 1.05 # 5% boost to home team strengths

# Scaling factors for the logistic function.
# A smaller number means the skill difference has a larger impact.
MIDFIELD_SCALING = 30
ATTACK_SCALING = 25
SHOT_SCALING = 20
# Adjusts the final shot conversion rate down to realistic levels (~15-25% conversion)
GOAL_CONVERSION_FACTOR = 0.45

def logistic_probability(strength_a, strength_b, scaling_factor):
    """Calculates the probability of A winning using a logistic function (S-curve)."""
    # Add randomness to the strengths to simulate fluctuating performance in this specific event
    rand_a = strength_a * random.uniform(0.85, 1.15)
    rand_b = strength_b * random.uniform(0.85, 1.15)

    diff = rand_a - rand_b
    # The logistic function: 1 / (1 + e^(-difference / scaling))
    try:
        # Handle potential large differences to prevent overflow in exp()
        if diff / scaling_factor < -10:
            prob = 0.0
        elif diff / scaling_factor > 10:
            prob = 1.0
        else:
            prob = 1 / (1 + math.exp(-diff / scaling_factor))
    except OverflowError:
        prob = 1.0 if diff > 0 else 0.0
    return prob

class MatchTeam:
    """Handles team preparation, lineup selection, and zonal strength calculation."""
    def __init__(self, team_model, is_home=False):
        self.team = team_model
        self.is_home = is_home
        self.lineup = {}
        self.zonal_strength = {}
        self.score = 0
        self.select_lineup()
        self.calculate_zonal_strength()

    def select_lineup(self):
        """Selects the best 11 players based on effective_skill for the defined formation."""
        # Use the effective_skill property which includes shape
        sorted_players = sorted(self.team.players, key=lambda p: p.effective_skill, reverse=True)

        self.lineup = {pos: [] for pos in Position}
        squad_count = 0

        # Select players based on formation requirements
        for pos, count in FORMATION.items():
            # Ensure we only select players not already in the lineup
            candidates = [p for p in sorted_players if p.position == pos and p not in self.get_starting_11()]
            selected = candidates[:count]
            self.lineup[pos].extend(selected)
            squad_count += len(selected)

        # Fallback: Fill remaining spots if formation requirements aren't met (e.g. injuries/lack of depth)
        if squad_count < 11:
            remaining_players = [p for p in sorted_players if p not in self.get_starting_11()]
            slots_to_fill = 11 - squad_count

            # Fill with remaining players regardless of position (best available)
            for player in remaining_players[:slots_to_fill]:
                self.lineup[player.position].append(player)

    def get_starting_11(self):
        starting_11 = []
        for players in self.lineup.values():
            starting_11.extend(players)
        return starting_11

    def calculate_zonal_strength(self):
        """Calculates the average effective_skill for each zone."""
        for pos in Position:
            players = self.lineup[pos]
            if players:
                avg_strength = sum(p.effective_skill for p in players) / len(players)
                self.zonal_strength[pos] = avg_strength
            else:
                # Default strength if no players are available
                self.zonal_strength[pos] = 10

            # Apply Home Advantage
            if self.is_home:
                self.zonal_strength[pos] *= HOME_ADVANTAGE_BOOST

    def get_random_player(self, positions):
        """Selects a random player from the lineup in the specified positions."""
        candidates = []
        for pos in positions:
            candidates.extend(self.lineup.get(pos, []))
        return random.choice(candidates) if candidates else None

    def get_goalkeeper(self):
        return self.lineup[Position.GOALKEEPER][0] if self.lineup[Position.GOALKEEPER] else None

class MatchSimulator:
    """Runs the match simulation using zonal battles and logistic probability."""
    def __init__(self, team_a_model, team_b_model):
        # Team A is Home, Team B is Away
        self.team_a = MatchTeam(team_a_model, is_home=True)
        self.team_b = MatchTeam(team_b_model, is_home=False)
        self.log = []
        self.minute = 0
        # State: 'M' (Midfield), 'A' (A attacking), 'B' (B attacking)
        self.zone = 'M'
        self.possession = random.choice([self.team_a, self.team_b])

    def log_event(self, message, importance='normal', event_type=None, details=None):
        """Logs a match event with optional structured details for analysis."""
        self.log.append({
            'minute': self.minute,
            'message': message,
            'importance': importance,
            'event_type': event_type,
            'details': details
        })

    def get_prematch_summary(self):
        summary = f"Prematch Analysis (Formation: 4-4-2). Home advantage active for {self.team_a.team.name}.\n"
        summary += f"--- {self.team_a.team.name} (H) Zonal Ratings (Effective Skill) ---\n"
        summary += f"DEF: {self.team_a.zonal_strength[Position.DEFENDER]:.1f}, MID: {self.team_a.zonal_strength[Position.MIDFIELDER]:.1f}, ATT: {self.team_a.zonal_strength[Position.FORWARD]:.1f}\n"
        summary += f"--- {self.team_b.team.name} (A) Zonal Ratings (Effective Skill) ---\n"
        summary += f"DEF: {self.team_b.zonal_strength[Position.DEFENDER]:.1f}, MID: {self.team_b.zonal_strength[Position.MIDFIELDER]:.1f}, ATT: {self.team_b.zonal_strength[Position.FORWARD]:.1f}"
        self.log_event(summary, importance='info', event_type='PREMATCH')

    def simulate(self):
        # Check for minimum players before starting
        if len(self.team_a.get_starting_11()) < 11 or len(self.team_b.get_starting_11()) < 11:
            self.log_event("Match abandoned: One or both teams could not field 11 players.", importance='error', event_type='ABANDONED')
            return self.get_results()

        self.get_prematch_summary()
        self.log_event("Kickoff!", importance='info', event_type='KICKOFF')

        while self.minute < 90:
            # Simulate time passing in variable increments (1-5 minutes)
            time_increment = random.randint(1, 5)
            self.minute += time_increment

            if self.minute > 90:
                self.minute = 90

            self.process_event()

            # Check for halftime
            if self.minute >= 45 and self.minute - time_increment < 45:
                self.log_event("Halftime", importance='info', event_type='HALF_TIME')

        self.log_event(f"Full Time! Final Score: {self.team_a.team.name} {self.team_a.score} - {self.team_b.score} {self.team_b.team.name}", importance='final', event_type='FULL_TIME')
        return self.get_results()

    def process_event(self):
        if self.zone == 'M':
            self.resolve_midfield_battle()
        elif self.zone == 'A':
            self.resolve_attack(self.team_a, self.team_b)
        elif self.zone == 'B':
            self.resolve_attack(self.team_b, self.team_a)

    def resolve_midfield_battle(self):
        attacker = self.possession
        defender = self.team_b if attacker == self.team_a else self.team_a

        att_mid = attacker.zonal_strength[Position.MIDFIELDER]
        def_mid = defender.zonal_strength[Position.MIDFIELDER]

        advance_prob = logistic_probability(att_mid, def_mid, MIDFIELD_SCALING)
        roll = random.random()
        result = "Success (Roll < Prob)" if roll < advance_prob else "Fail (Roll >= Prob)"

        details = (
            f"Midfield Contest: {attacker.team.name} (Att) vs {defender.team.name} (Def)\n"
            f"  - Att Mid Strength: {att_mid:.1f} vs Def Mid Strength: {def_mid:.1f}\n"
            f"  - Probability to Advance: {advance_prob:.1%}\n"
            f"  - Dice Roll (0.0-1.0): {roll:.3f} -> {result}"
        )

        if roll < advance_prob:
            # Advance to attacking zone
            self.zone = 'A' if attacker == self.team_a else 'B'
            player = attacker.get_random_player([Position.MIDFIELDER])
            message = f"{player.name} drives {attacker.team.name} into the attacking third." if player else f"{attacker.team.name} advances."
            self.log_event(message, event_type='ADVANCE', details=details)
        else:
            # Turnover
            self.possession = defender
            player = defender.get_random_player([Position.MIDFIELDER, Position.DEFENDER])
            message = f"{player.name} intercepts for {defender.team.name} in the midfield." if player else f"{defender.team.name} wins the ball back."
            self.log_event(message, event_type='TURNOVER', details=details)

    def resolve_attack(self, attacker_team, defender_team):
        att_str = attacker_team.zonal_strength[Position.FORWARD]
        def_str = defender_team.zonal_strength[Position.DEFENDER]

        shot_chance_prob = logistic_probability(att_str, def_str, ATTACK_SCALING)
        roll = random.random()
        result = "Success (Roll < Prob)" if roll < shot_chance_prob else "Fail (Roll >= Prob)"

        details = (
            f"Attack Phase: {attacker_team.team.name} (Att) vs {defender_team.team.name} (Def)\n"
            f"  - Att Fwd Strength: {att_str:.1f} vs Def Strength: {def_str:.1f}\n"
            f"  - Probability to Create Chance: {shot_chance_prob:.1%}\n"
            f"  - Dice Roll (0.0-1.0): {roll:.3f} -> {result}"
        )

        if roll < shot_chance_prob:
            self.log_event(
                f"{attacker_team.team.name} breaks through the defense!",
                event_type='SHOT_OPPORTUNITY',
                details=details
            )
            self.resolve_shot(attacker_team, defender_team)
        else:
            player = defender_team.get_random_player([Position.DEFENDER])
            message = f"Solid defending by {player.name}. {defender_team.team.name} clears the danger." if player else f"The defense holds firm for {defender_team.team.name}."
            self.log_event(message, event_type='DEFENSIVE_STOP', details=details)
            self.possession = defender_team
            self.zone = 'M'

    def resolve_shot(self, attacker_team, defender_team):
        if random.random() < 0.7:
            shooter = attacker_team.get_random_player([Position.FORWARD])
        else:
            shooter = attacker_team.get_random_player([Position.MIDFIELDER])

        goalkeeper = defender_team.get_goalkeeper()

        if not shooter or not goalkeeper:
            self.log_event("The attack fizzles out awkwardly.", importance='miss', event_type='ERROR', details="Could not select a valid shooter or goalkeeper.")
            self.possession = defender_team
            self.zone = 'M'
            return

        shooting_skill = shooter.effective_skill
        gk_skill = goalkeeper.effective_skill

        initial_prob = logistic_probability(shooting_skill, gk_skill, SHOT_SCALING)
        goal_prob = initial_prob * GOAL_CONVERSION_FACTOR
        roll = random.random()
        result = "GOAL (Roll < Prob)" if roll < goal_prob else "NO GOAL (Roll >= Prob)"

        details = (
            f"Shot Resolution: {shooter.name} (Shooter, {shooting_skill:.1f}) vs {goalkeeper.name} (GK, {gk_skill:.1f})\n"
            f"  - Base Goal Prob (raw skill matchup): {initial_prob:.1%}\n"
            f"  - Final Goal Prob (x{GOAL_CONVERSION_FACTOR} realism factor): {goal_prob:.1%}\n"
            f"  - Dice Roll (0.0-1.0): {roll:.3f} -> {result}"
        )

        if roll < goal_prob:
            attacker_team.score += 1
            score_line = f"({self.team_a.score}-{self.team_b.score})"
            message = f"GOOOOAL!!! {shooter.name} ({attacker_team.team.name}) finds the back of the net! {score_line}"
            self.log_event(message, importance='goal', event_type='GOAL', details=details)
            self.possession = defender_team
            self.zone = 'M'
        else:
            save_vs_miss_prob = gk_skill / (shooting_skill + gk_skill) if (shooting_skill + gk_skill) > 0 else 0.5
            save_roll = random.random()
            save_result = "SAVE (Roll < Prob)" if save_roll < save_vs_miss_prob else "MISS (Roll >= Prob)"

            outcome_details = (
                f"\nOutcome: Save or Miss?\n"
                f"  - GK Dominance vs Shooter Error: {save_vs_miss_prob:.1%}\n"
                f"  - Dice Roll (0.0-1.0): {save_roll:.3f} -> {save_result}"
            )
            details += outcome_details

            if save_roll < save_vs_miss_prob:
                message = f"SAVE! A fantastic stop by {goalkeeper.name} to deny {shooter.name}!"
                self.log_event(message, importance='save', event_type='SAVE', details=details)
            else:
                message = f"MISS! {shooter.name} sends the shot wide/high."
                self.log_event(message, importance='miss', event_type='MISS', details=details)

            self.possession = defender_team
            self.zone = 'M'

    def get_results(self):
        return {
            'log': self.log,
            'score_a': self.team_a.score,
            'score_b': self.team_b.score,
            'team_a_name': self.team_a.team.name,
            'team_b_name': self.team_b.team.name
        }

def simulate_match(team_a_id, team_b_id):
    team_a = Team.query.get(team_a_id)
    team_b = Team.query.get(team_b_id)

    if not team_a or not team_b:
        return {
            'log': [{'minute': 0, 'message': 'Invalid Teams Provided', 'importance': 'error', 'details': None, 'event_type': 'ERROR'}],
            'score_a': 0, 'score_b': 0,
            'team_a_name': team_a.name if team_a else 'Unknown',
            'team_b_name': team_b.name if team_b else 'Unknown'
        }

    simulator = MatchSimulator(team_a, team_b)
    return simulator.simulate()
