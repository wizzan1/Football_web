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
HOME_ADVANTAGE_BOOST = 1.04

# ----- Flow & scoring (non-GK specific) ---------------------------------------

# MIDFIELD_SCALING controls how often play advances.
MIDFIELD_SCALING = 32

# ATTACK_SCALING controls how often an attack turns into a shot opportunity.
ATTACK_SCALING = 32

# Global conversion multiplier.
GOAL_CONVERSION_FACTOR = 1.00

# -------------------------------
# Goalkeeper-specific tuning knobs
# -------------------------------

# 1) GK contribution to defensive gate during chance creation.
DEF_GK_BLEND = 0.18

# 2) Dedicated GK scaling for shots.
GK_SHOT_SCALING = 30

# Shooter/Taker per-shot variance. (±15%)
SHOOTER_NOISE_MIN = 0.85
SHOOTER_NOISE_MAX = 1.15

# GK per-shot variance. (±8%)
GK_NOISE_MIN = 0.92
GK_NOISE_MAX = 1.08

# -------------------------------
# Free Kick (FK) Tuning Knobs (NEW)
# -------------------------------

# Average number of free kicks per game (based on real-world data 25-33)
AVG_FREE_KICKS_PER_GAME = 10
# Variance in the number of free kicks
FREE_KICK_VARIANCE = 5

# Distance categorization and probabilities (Distance is abstract, 0=own goal line, 100=opponent goal line)
# Zone definitions and likelihood of a FK happening in that zone
FK_ZONES = {
    # Zone Name: (Likelihood, P(Direct Shot), P(Indirect Attack/Cross), Defense Modifier for Cross)
    'DEEP':      (0.25, 0.00, 0.05, 1.00), # Defensive half (only 5% lead to an immediate attack)
    'MIDDLE':    (0.50, 0.02, 0.40, 0.90), # Midfield
    'ATTACKING': (0.17, 0.30, 0.70, 0.75), # Attacking third (e.g., 25-40m)
    'DANGEROUS': (0.08, 0.85, 0.15, 0.60), # Close to the box (e.g., <25m)
}

# Scaling factor for FK shots (slightly different than open play)
FK_SHOT_SCALING = 24

# Base conversion factor for FK (Lower than open play, as direct FKs are harder to score)
# This will be further modified by distance within the resolution function.
FK_GOAL_CONVERSION_FACTOR_BASE = 0.60


def logistic_probability(strength_a, strength_b, scaling_factor):
    """
    Calculates the probability of A overcoming B using a logistic function.
    """
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


def goal_probability(shooter_eff: float, keeper_eff: float, scaling=GK_SHOT_SCALING, conversion_factor=GOAL_CONVERSION_FACTOR) -> float:
    """
    Shooter vs GK probability model.
    Modified to accept custom scaling and conversion factors (for FKs).
    """
    # Noise is applied here to represent variance in the moment of the shot
    rand_shooter = shooter_eff * random.uniform(SHOOTER_NOISE_MIN, SHOOTER_NOISE_MAX)
    rand_keeper = keeper_eff * random.uniform(GK_NOISE_MIN, GK_NOISE_MAX)
    diff = rand_shooter - rand_keeper

    try:
        exponent = -diff / scaling
        if exponent > 10:
            base = 0.0
        elif exponent < -10:
            base = 1.0
        else:
            base = 1 / (1 + math.exp(exponent))
    except OverflowError:
        base = 1.0 if diff > 0 else 0.0

    # Ensure probability doesn't exceed 1.0
    return min(1.0, base * conversion_factor)


# === MatchTeam Class ===

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
        self.best_fk_taker = self._find_best_fk_taker() # NEW

    def get_starting_11(self):
        return [p for players in self.lineup.values() for p in players]

    def _find_best_fk_taker(self):
        # NEW: Finds the player on the pitch with the highest free_kick_ability (not effective)
        starting_11 = self.get_starting_11()
        if not starting_11:
            return None
        # We use getattr as a safeguard, although the model defines the default.
        return max(starting_11, key=lambda p: getattr(p, 'free_kick_ability', 50))

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
            # Default: 20 (A more reasonable baseline if a zone is somehow empty)
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
        # Updated to include FK ability in the lineup data
        return {
            'name': self.team.name, 'is_home': self.is_home,
            'avg_base_skill': self.avg_base_skill, 'avg_shape': self.avg_shape, 'avg_effective_skill': self.avg_effective_skill,
            'base_zonal_strength': {pos.name: strength for pos, strength in self.base_zonal_strength.items()},
            'zonal_strength': {pos.name: strength for pos, strength in self.zonal_strength.items()},
            'lineup': [{'name': p.name, 'position': p.position.value, 'skill': p.skill, 'shape': p.shape, 'fk_ability': getattr(p, 'free_kick_ability', 50), 'id': p.id} for p in self.get_starting_11()]
        }

# === MatchSimulator Class ===

class MatchSimulator:
    def __init__(self, team_a_model, team_b_model, logging_enabled=True, fixed_a_ids=None, fixed_b_ids=None):
        self.team_a = MatchTeam(team_a_model, is_home=True, fixed_lineup_ids=fixed_a_ids)
        self.team_b = MatchTeam(team_b_model, is_home=False, fixed_lineup_ids=fixed_b_ids)
        self.logging_enabled = logging_enabled
        self.log = []
        self.minute = 0
        self.zone = 'M'
        self.possession = random.choice([self.team_a, self.team_b])
        self.free_kick_events = self._generate_free_kicks() # NEW

    def _generate_free_kicks(self):
        """Pre-calculates all free kick events for the match."""
        # Use Gaussian distribution for realistic variation in total FK count
        num_kicks = int(random.gauss(AVG_FREE_KICKS_PER_GAME, FREE_KICK_VARIANCE))
        num_kicks = max(10, num_kicks) # Ensure a minimum number

        events = []
        zone_names = list(FK_ZONES.keys())
        likelihoods = [FK_ZONES[z][0] for z in zone_names]

        for _ in range(num_kicks):
            # 1. Determine time
            minute = random.randint(1, 90)

            # 2. Determine team (50/50 split)
            taking_team = self.team_a if random.random() < 0.5 else self.team_b

            # 3. Determine location (Zone)
            zone_name = random.choices(zone_names, weights=likelihoods, k=1)[0]

            events.append({
                'minute': minute,
                'team': taking_team,
                'zone': zone_name
            })

        # Sort by time
        events.sort(key=lambda e: e['minute'])
        return events

    def log_event(self, message, importance='normal', event_type=None, details=None):
        if not self.logging_enabled:
            return
        self.log.append({'minute': self.minute, 'message': message, 'importance': importance, 'event_type': event_type, 'details': details})

    def simulate(self):
        if len(self.team_a.get_starting_11()) < 11 or len(self.team_b.get_starting_11()) < 11:
            self.log_event("Match abandoned due to insufficient players.", importance='error')
            return self.get_results()

        if self.logging_enabled:
            self.log_event(f"Kickoff! (Total FKs scheduled: {len(self.free_kick_events)})", importance='info')

        while self.minute < 90:
            # 1. Process scheduled free kicks (NEW)
            self._process_scheduled_free_kicks()

            if self.minute >= 90:
                break

            # 2. Proceed with open play
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

    def _process_scheduled_free_kicks(self):
        """Handles free kicks scheduled up to the current simulation minute."""
        while self.free_kick_events and self.free_kick_events[0]['minute'] <= self.minute:
            fk_event = self.free_kick_events.pop(0)

            # Set the simulation time exactly to the time of the FK
            self.minute = fk_event['minute']

            self.resolve_free_kick(fk_event)

    def process_event(self):
        # Ensure possession is always set before open play
        if not self.possession:
            self.possession = random.choice([self.team_a, self.team_b])

        if self.zone == 'M':
            self.resolve_midfield_battle()
        elif self.zone == 'A':
            self.resolve_attack(self.team_a, self.team_b)
        elif self.zone == 'B':
            self.resolve_attack(self.team_b, self.team_a)

    # ===========================
    # Free Kick Resolution (NEW)
    # ===========================

    def resolve_free_kick(self, fk_event):
        attacker = fk_event['team']
        defender = self.team_b if attacker == self.team_a else self.team_a
        zone = fk_event['zone']

        # Retrieve probabilities from config: (Likelihood, P(Direct), P(Indirect), DefMod)
        _, p_direct, p_indirect_attack, defense_modifier = FK_ZONES[zone]

        self.log_event(f"Free Kick to {attacker.team.name} in a {zone.lower()} position.", event_type='FREE_KICK', importance='set_piece')

        # Decide action: Direct Shot, Indirect Attack (Cross), or Simple Restart
        action_roll = random.random()

        if action_roll < p_direct:
            self.resolve_direct_free_kick(attacker, defender, zone)
        elif action_roll < (p_direct + p_indirect_attack):
            # Indirect Attack (Cross)
            self.log_event(f"{attacker.team.name} sends a cross or pass into the attacking zone.", event_type='INDIRECT_FK_ATTACK')
            self.possession = attacker
            self.zone = 'A' if attacker == self.team_a else 'B'
            # Resolve attack immediately with the corresponding defense modifier
            self.resolve_attack(attacker, defender, defense_modifier=defense_modifier)
        else:
            # Simple restart (pass back or safe pass)
            self.log_event(f"{attacker.team.name} restarts play safely from the free kick.", event_type='FK_RESTART', importance='minor')
            self.possession = attacker
            self.zone = 'M'

    def resolve_direct_free_kick(self, attacker, defender, zone):
        taker = attacker.best_fk_taker
        goalkeeper = defender.get_goalkeeper()

        if not taker or not goalkeeper:
            return

        self.log_event(f"{taker.name} steps up to take the direct free kick.", importance='high', event_type='DIRECT_FK')

        # Adjust the conversion factor based on the zone (distance)
        # Dangerous zones get a boost, far zones get a penalty.
        if zone == 'DANGEROUS':
            distance_factor = 1.3
        elif zone == 'ATTACKING':
            distance_factor = 0.8
        elif zone == 'MIDDLE':
            distance_factor = 0.3
        else:
            distance_factor = 0.1

        final_conversion_factor = FK_GOAL_CONVERSION_FACTOR_BASE * distance_factor

        # Calculate Probability using the taker's effective FK ability and the GK's effective skill
        # We use the specialized FK parameters for scaling and conversion.
        prob = goal_probability(
            taker.effective_fk_ability,
            goalkeeper.effective_skill,
            scaling=FK_SHOT_SCALING,
            conversion_factor=final_conversion_factor
        )

        roll = random.random()

        if roll < prob:
            attacker.score += 1
            if self.logging_enabled:
                details = (
                    f"Direct Free Kick ({zone}): {taker.name} (FK Eff: {taker.effective_fk_ability:.1f}) vs {goalkeeper.name} (GK Eff: {goalkeeper.effective_skill:.1f})\n"
                    f"- FK Scaling: {FK_SHOT_SCALING}, Final Conv Factor: {final_conversion_factor:.2f} (Dist Factor: {distance_factor:.2f})\n"
                    f"- Goal Prob: {prob:.1%}\n"
                    f"- Roll: {roll:.3f} -> GOAL"
                )
                score_line = f"({self.team_a.score}-{self.team_b.score})"
                self.log_event(f"GOAL! Stunning free kick by {taker.name}! {score_line}", importance='goal', event_type='GOAL_FK', details=details)
            self.possession = defender
            self.zone = 'M'
        else:
            if self.logging_enabled:
                details = (
                    f"Direct Free Kick ({zone}): {taker.name} (FK Eff: {taker.effective_fk_ability:.1f}) vs {goalkeeper.name} (GK Eff: {goalkeeper.effective_skill:.1f})\n"
                    f"- FK Scaling: {FK_SHOT_SCALING}, Final Conv Factor: {final_conversion_factor:.2f} (Dist Factor: {distance_factor:.2f})\n"
                    f"- Goal Prob: {prob:.1%}\n"
                    f"- Roll: {roll:.3f} -> NO GOAL"
                )
                outcome = "Saved" if random.random() > 0.5 else "Missed"
                self.log_event(f"NO GOAL! {taker.name}'s free kick is {outcome.lower()}.", importance='miss', event_type='MISS_FK', details=details)
            # Simplified to GK possession (save or goal kick)
            self.possession = defender
            self.zone = 'M'

    # ===========================
    # Open Play Resolution
    # ===========================

    def resolve_midfield_battle(self):
        attacker, defender = (self.possession, self.team_b) if self.possession == self.team_a else (self.possession, self.team_a)
        att_str = attacker.zonal_strength[Position.MIDFIELDER]
        def_str = defender.zonal_strength[Position.MIDFIELDER]

        prob = logistic_probability(att_str, def_str, MIDFIELD_SCALING)
        roll = random.random()

        if roll < prob:
            self.zone = 'A' if attacker == self.team_a else 'B'
            result_text = "Success"
        else:
            self.possession = defender
            result_text = "Fail"

        if self.logging_enabled:
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

    # Updated to accept an optional defense_modifier (for indirect free kicks)
    def resolve_attack(self, attacker, defender, defense_modifier=1.0):
        att_str = attacker.zonal_strength[Position.FORWARD]

        pure_def = defender.zonal_strength[Position.DEFENDER]
        gk_str = defender.zonal_strength[Position.GOALKEEPER]
        def_gate_base = (1.0 - DEF_GK_BLEND) * pure_def + DEF_GK_BLEND * gk_str

        # Apply modifier (used for indirect free kicks/crosses)
        def_gate = def_gate_base * defense_modifier

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

            # Show modifier in logs if it was applied
            modifier_text = f" (Base {def_gate_base:.1f} * Mod {defense_modifier:.2f})" if defense_modifier != 1.0 else ""

            return (
                f"Attack (Scale: {ATTACK_SCALING}): {attacker.team.name} vs {defender.team.name}\n"
                f"- Att Fwd: {att_d}\n"
                f"- Def Gate: DEF {def_d} + GK {gk_d} (blend {DEF_GK_BLEND:.0%}) -> {def_gate:.1f}{modifier_text}\n"
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

        # Uses default parameters for open play shots
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
