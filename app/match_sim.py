# app/match_sim.py
import random
import math
# Note: We rely on the models having access to the DB context (e.g., Team.query.get)
from .models import Team, Player, Position

# ===========================
# Configuration / Tunables
# ===========================

# Formation used to pick starting 11
FORMATION = {
    Position.GOALKEEPER: 1,
    Position.DEFENDER: 4,
    Position.MIDFIELDER: 4,
    Position.FORWARD: 2
}

# Home advantage multiplier
# OLD: 1.01 (Negligible)
# NEW: 1.06 (A meaningful 6% boost)
HOME_ADVANTAGE_BOOST = 1.04

# ----- Flow & scoring (non-GK specific) ---------------------------------------
# We increase scaling factors (from 22) to flatten the sensitivity curve.

# MIDFIELD_SCALING controls how often play advances.
MIDFIELD_SCALING = 32

# ATTACK_SCALING controls how often an attack turns into a shot opportunity.
ATTACK_SCALING = 32

# Legacy global shot scaling.
SHOT_SCALING = 24

# Global conversion multiplier.
# OLD: 0.97
# NEW: 1.00 (Set to 1.0 to help reach the target goal average, compensating for higher scaling)
GOAL_CONVERSION_FACTOR = 1.00

# -------------------------------
# Goalkeeper-specific tuning knobs
# -------------------------------

# 1) GK contribution to defensive gate during chance creation.
DEF_GK_BLEND = 0.18

# 2) Dedicated GK scaling for shots.
# OLD: 22
# NEW: 30 (Increased to flatten the curve, but slightly less than Mid/Att)
GK_SHOT_SCALING = 30

# Shooter per-shot variance. (Kept as is, ±15%)
SHOOTER_NOISE_MIN = 0.85
SHOOTER_NOISE_MAX = 1.15

# GK per-shot variance. (Kept as is, ±8%)
GK_NOISE_MIN = 0.92
GK_NOISE_MAX = 1.08


def logistic_probability(strength_a, strength_b, scaling_factor):
    """
    Calculates the probability of A overcoming B using a logistic function.
    CRITICAL CHANGE: Removed internal randomization (noise).
    """
    # rand_a = strength_a * random.uniform(0.85, 1.15) # REMOVED
    # rand_b = strength_b * random.uniform(0.85, 1.15) # REMOVED
    diff = strength_a - strength_b
    try:
        # Clamping the exponent to prevent extreme values and overflow errors
        exponent = -diff / scaling_factor
        if exponent > 10:
            return 0.0
        elif exponent < -10:
            return 1.0
        else:
            return 1 / (1 + math.exp(exponent))
    except OverflowError:
        # Safeguard
        return 1.0 if diff > 0 else 0.0


def goal_probability(shooter_eff: float, keeper_eff: float) -> float:
    """
    Shooter vs GK probability model. We KEEP the noise here as it represents
    individual variance in a high-stakes moment (the shot).
    """
    rand_shooter = shooter_eff * random.uniform(SHOOTER_NOISE_MIN, SHOOTER_NOISE_MAX)
    rand_keeper = keeper_eff * random.uniform(GK_NOISE_MIN, GK_NOISE_MAX)
    diff = rand_shooter - rand_keeper

    try:
        exponent = -diff / GK_SHOT_SCALING
        if exponent > 10:
            base = 0.0
        elif exponent < -10:
            base = 1.0
        else:
            base = 1 / (1 + math.exp(exponent))
    except OverflowError:
        base = 1.0 if diff > 0 else 0.0

    # Ensure probability doesn't exceed 1.0
    return min(1.0, base * GOAL_CONVERSION_FACTOR)


# === MatchTeam Class (Included for completeness, minor change to default strength) ===

class MatchTeam:
    def __init__(self, team_model, is_home=False, fixed_lineup_ids=None):
        self.team = team_model
        self.is_home = is_home
        self.fixed_lineup_ids = fixed_lineup_ids
        self.lineup = {}
        self.base_zonal_strength = {}
        self.zonal_strength = {}
        self.avg_shape = 0
        self.avg_base_skill = 0
        self.avg_effective_skill = 0
        self.score = 0
        self.select_lineup()
        self.calculate_zonal_strength()

    def get_starting_11(self):
        return [p for players in self.lineup.values() for p in players]

    def select_lineup(self):
        if self.fixed_lineup_ids:
            fixed_players = [p for p in self.team.players if p.id in self.fixed_lineup_ids]
            self.lineup = {pos: [] for pos in Position}
            for p in fixed_players:
                self.lineup[p.position].append(p)
        else:
            # This now uses the updated effective_skill calculation from models.py
            sorted_players = sorted(self.team.players, key=lambda p: p.effective_skill, reverse=True)
            self.lineup = {pos: [] for pos in Position}
            squad_count = 0
            for pos, count in FORMATION.items():
                candidates = [p for p in sorted_players if p.position == pos and p not in self.get_starting_11()]
                selected = candidates[:count]
                self.lineup[pos].extend(selected)
                squad_count += len(selected)
            if squad_count < 11:
                remaining_players = [p for p in sorted_players if p not in self.get_starting_11()]
                for player in remaining_players[:11 - squad_count]:
                    self.lineup[player.position].append(player)

        starting_11 = self.get_starting_11()
        if starting_11:
            self.avg_base_skill = sum(p.skill for p in starting_11) / len(starting_11)
            self.avg_shape = sum(p.shape for p in starting_11) / len(starting_11)
            self.avg_effective_skill = sum(p.effective_skill for p in starting_11) / len(starting_11)

    def calculate_zonal_strength(self):
        for pos in Position:
            players = self.lineup.get(pos, [])
            # OLD default: 10
            # NEW default: 20 (A more reasonable baseline if a zone is somehow empty)
            base_strength = sum(p.effective_skill for p in players) / len(players) if players else 20
            self.base_zonal_strength[pos] = base_strength
            self.zonal_strength[pos] = base_strength * HOME_ADVANTAGE_BOOST if self.is_home else base_strength

    def get_random_player(self, positions):
        candidates = [p for pos in positions for p in self.lineup.get(pos, [])]
        return random.choice(candidates) if candidates else None

    def get_goalkeeper(self):
        gk_list = self.lineup.get(Position.GOALKEEPER, [])
        return gk_list[0] if gk_list else None

    def get_stats_dict(self):
        return {
            'name': self.team.name, 'is_home': self.is_home,
            'avg_base_skill': self.avg_base_skill, 'avg_shape': self.avg_shape, 'avg_effective_skill': self.avg_effective_skill,
            'base_zonal_strength': {pos.name: strength for pos, strength in self.base_zonal_strength.items()},
            'zonal_strength': {pos.name: strength for pos, strength in self.zonal_strength.items()},
            'lineup': [{'name': p.name, 'position': p.position.value, 'skill': p.skill, 'shape': p.shape, 'id': p.id} for p in self.get_starting_11()]
        }

# === MatchSimulator Class (Includes improved logging to show new constants) ===

class MatchSimulator:
    def __init__(self, team_a_model, team_b_model, logging_enabled=True, fixed_a_ids=None, fixed_b_ids=None):
        self.team_a = MatchTeam(team_a_model, is_home=True, fixed_lineup_ids=fixed_a_ids)
        self.team_b = MatchTeam(team_b_model, is_home=False, fixed_lineup_ids=fixed_b_ids)
        self.logging_enabled = logging_enabled
        self.log = []
        self.minute = 0
        self.zone = 'M'
        self.possession = random.choice([self.team_a, self.team_b])

    def log_event(self, message, importance='normal', event_type=None, details=None):
        if not self.logging_enabled:
            return
        self.log.append({'minute': self.minute, 'message': message, 'importance': importance, 'event_type': event_type, 'details': details})

    def simulate(self):
        if len(self.team_a.get_starting_11()) < 11 or len(self.team_b.get_starting_11()) < 11:
            self.log_event("Match abandoned due to insufficient players.", importance='error')
            return self.get_results()

        if self.logging_enabled:
            self.log_event("Kickoff!", importance='info')

        while self.minute < 90:
            # Increased time increment slightly (1-5) -> (1-6) for slightly more variance
            time_increment = random.randint(1, 6)
            last_minute = self.minute
            self.minute += time_increment
            if self.minute > 90:
                self.minute = 90

            if self.logging_enabled and last_minute < 45 and self.minute >= 45:
                self.log_event("Halftime", importance='info')

            self.process_event()

        if self.logging_enabled:
            self.log_event(f"Full Time! Final score: {self.team_a.score} - {self.team_b.score}", importance='final')

        return self.get_results()

    def process_event(self):
        if self.zone == 'M':
            self.resolve_midfield_battle()
        elif self.zone == 'A':
            self.resolve_attack(self.team_a, self.team_b)
        elif self.zone == 'B':
            self.resolve_attack(self.team_b, self.team_a)

    def resolve_midfield_battle(self):
        attacker, defender = (self.possession, self.team_b) if self.possession == self.team_a else (self.possession, self.team_a)
        att_str = attacker.zonal_strength[Position.MIDFIELDER]
        def_str = defender.zonal_strength[Position.MIDFIELDER]

        # Uses the updated logistic_probability (no noise) and new MIDFIELD_SCALING
        prob = logistic_probability(att_str, def_str, MIDFIELD_SCALING)
        roll = random.random()

        if roll < prob:
            self.zone = 'A' if attacker == self.team_a else 'B'
            result_text = "Success"
        else:
            self.possession = defender
            result_text = "Fail"

        if self.logging_enabled:
            # Improved logging to show the actual boost factor used and the scaling factor
            att_d = f"{attacker.base_zonal_strength[Position.MIDFIELDER]:.1f} * {HOME_ADVANTAGE_BOOST:.2f} (H) -> {att_str:.1f}" if attacker.is_home else f"{att_str:.1f}"
            def_d = f"{defender.base_zonal_strength[Position.MIDFIELDER]:.1f} * {HOME_ADVANTAGE_BOOST:.2f} (H) -> {def_str:.1f}" if defender.is_home else f"{def_str:.1f}"
            details = (
                f"Midfield (Scale: {MIDFIELD_SCALING}): {attacker.team.name} vs {defender.team.name}\n"
                f"- Att Str: {att_d}\n"
                f"- Def Str: {def_d}\n"
                f"- Prob to Advance: {prob:.1%}\n"
                f"- Roll: {roll:.3f} -> {result_text}"
            )
            message = f"{attacker.team.name} advances." if result_text == "Success" else f"{defender.team.name} wins the ball."
            self.log_event(message, details=details)

    def resolve_attack(self, attacker, defender):
        att_str = attacker.zonal_strength[Position.FORWARD]

        pure_def = defender.zonal_strength[Position.DEFENDER]
        gk_str = defender.zonal_strength[Position.GOALKEEPER]
        def_gate = (1.0 - DEF_GK_BLEND) * pure_def + DEF_GK_BLEND * gk_str

        # Uses the updated logistic_probability (no noise) and new ATTACK_SCALING
        prob = logistic_probability(att_str, def_gate, ATTACK_SCALING)
        roll = random.random()

        # Helper to format logging details (DRY principle)
        def get_attack_details(success):
            att_d = f"{attacker.base_zonal_strength[Position.FORWARD]:.1f} * {HOME_ADVANTAGE_BOOST:.2f} (H) -> {att_str:.1f}" if attacker.is_home else f"{att_str:.1f}"
            def_base = f"{defender.base_zonal_strength[Position.DEFENDER]:.1f}"
            gk_base = f"{defender.base_zonal_strength[Position.GOALKEEPER]:.1f}"
            if defender.is_home:
                def_d = f"{def_base} * {HOME_ADVANTAGE_BOOST:.2f} (H) -> {pure_def:.1f}"
                gk_d = f"{gk_base} * {HOME_ADVANTAGE_BOOST:.2f} (H) -> {gk_str:.1f}"
            else:
                def_d = f"{pure_def:.1f}"
                gk_d = f"{gk_str:.1f}"
            return (
                f"Attack (Scale: {ATTACK_SCALING}): {attacker.team.name} vs {defender.team.name}\n"
                f"- Att Fwd: {att_d}\n"
                f"- Def Gate: DEF {def_d} + GK {gk_d} (blend {DEF_GK_BLEND:.0%}) -> {def_gate:.1f}\n"
                f"- Prob to Create Chance: {prob:.1%}\n"
                f"- Roll: {roll:.3f} -> {'Success' if success else 'Fail'}"
            )

        if roll < prob:
            if self.logging_enabled:
                self.log_event(f"{attacker.team.name} creates a chance!", event_type='SHOT_OPPORTUNITY', details=get_attack_details(True))
            self.resolve_shot(attacker, defender)
        else:
            self.possession = defender
            self.zone = 'M'
            if self.logging_enabled:
                self.log_event(f"{defender.team.name}'s defense holds firm.", event_type='DEFENSIVE_STOP', details=get_attack_details(False))

    def resolve_shot(self, attacker, defender):
        shooter = attacker.get_random_player([Position.FORWARD, Position.MIDFIELDER])
        goalkeeper = defender.get_goalkeeper()
        if not shooter or not goalkeeper:
            self.possession = defender
            self.zone = 'M'
            return

        # Uses the updated goal_probability (with noise) and new GK_SHOT_SCALING/GOAL_CONVERSION_FACTOR
        prob = goal_probability(shooter.effective_skill, goalkeeper.effective_skill)
        roll = random.random()

        if roll < prob:
            attacker.score += 1
            if self.logging_enabled:
                details = (
                    f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n"
                    f"- GK Scaling: {GK_SHOT_SCALING}, Conv Factor: {GOAL_CONVERSION_FACTOR:.2f}\n"
                    f"- Goal Prob: {prob:.1%}\n"
                    f"- Roll: {roll:.3f} -> GOAL"
                )
                score_line = f"({self.team_a.score}-{self.team_b.score})"
                self.log_event(f"GOAL! {shooter.name} scores! {score_line}", importance='goal', event_type='GOAL', details=details)
        else:
            if self.logging_enabled:
                details = (
                    f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n"
                    f"- GK Scaling: {GK_SHOT_SCALING}, Conv Factor: {GOAL_CONVERSION_FACTOR:.2f}\n"
                    f"- Goal Prob: {prob:.1%}\n"
                    f"- Roll: {roll:.3f} -> NO GOAL"
                )
                self.log_event(f"NO GOAL! Shot by {shooter.name}.", importance='miss', event_type='MISS', details=details)

        self.possession = defender
        self.zone = 'M'

    def get_results(self):
        return {
            'log': self.log,
            'score_a': self.team_a.score,
            'score_b': self.team_b.score,
            'team_a_name': self.team_a.team.name,
            'team_b_name': self.team_b.team.name
        }


# === Helper Functions (Included for completeness) ===
# These functions rely on database access (Team.query.get).

def simulate_match(team_a_id, team_b_id):
    # Assuming Team.query works here (requires active app context)
    team_a, team_b = Team.query.get(team_a_id), Team.query.get(team_b_id)
    if not team_a or not team_b:
        return {'log': [{'message': 'Invalid Teams'}], 'score_a': 0, 'score_b': 0, 'team_a_name': '?', 'team_b_name': '?'}
    return MatchSimulator(team_a, team_b, logging_enabled=True).simulate()


def get_prematch_odds(user_team_id=None, enemy_team_id=None, simulations=100, user_team_model=None, enemy_team_model=None, fixed_user_lineup_ids=None):
    if not user_team_model and user_team_id:
        user_team_model = Team.query.get(user_team_id)
    if not enemy_team_model and enemy_team_id:
        enemy_team_model = Team.query.get(enemy_team_id)

    if not user_team_model or not enemy_team_model:
        return {'error': 'Invalid teams'}

    # Calculate MatchTeam stats once
    user_team_home = MatchTeam(user_team_model, is_home=True, fixed_lineup_ids=fixed_user_lineup_ids)
    user_team_away = MatchTeam(user_team_model, is_home=False, fixed_lineup_ids=fixed_user_lineup_ids)
    enemy_team_home = MatchTeam(enemy_team_model, is_home=True)
    enemy_team_away = MatchTeam(enemy_team_model, is_home=False)

    def _run_fixture_sims(home_team_model, away_team_model, fixed_home_ids=None, fixed_away_ids=None):
        wins, draws, losses, goals_for, goals_against = 0, 0, 0, 0, 0
        for _ in range(simulations):
            # The simulator will now use the updated logic and constants
            simulator = MatchSimulator(home_team_model, away_team_model, logging_enabled=False, fixed_a_ids=fixed_home_ids, fixed_b_ids=fixed_away_ids)
            result = simulator.simulate()
            goals_for += result['score_a']
            goals_against += result['score_b']
            if result['score_a'] > result['score_b']:
                wins += 1
            elif result['score_b'] > result['score_a']:
                losses += 1
            else:
                draws += 1
        return {
            'win_prob': (wins / simulations) * 100,
            'draw_prob': (draws / simulations) * 100,
            'loss_prob': (losses / simulations) * 100,
            'avg_goals_for': goals_for / simulations,
            'avg_goals_against': goals_against / simulations
        }

    home_fixture_probs = _run_fixture_sims(user_team_model, enemy_team_model, fixed_home_ids=fixed_user_lineup_ids, fixed_away_ids=None)
    away_fixture_probs = _run_fixture_sims(enemy_team_model, user_team_model, fixed_home_ids=None, fixed_away_ids=fixed_user_lineup_ids)

    return {
        'home_fixture': {
            'probs': home_fixture_probs,
            'stats': {'user_team': user_team_home.get_stats_dict(), 'enemy_team': enemy_team_away.get_stats_dict()}
        },
        'away_fixture': {
            'probs': away_fixture_probs,
            'stats': {'user_team': user_team_away.get_stats_dict(), 'enemy_team': enemy_team_home.get_stats_dict()}
        },
        'simulations_run': simulations
    }
