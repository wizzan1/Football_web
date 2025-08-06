# textfootball/core/match_simulator.py

import random
import math
from textfootball.models import Team, Player, Position

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
MIDFIELD_SCALING = 32
ATTACK_SCALING = 32
GOAL_CONVERSION_FACTOR = 1.00

# -------------------------------
# Goalkeeper-specific tuning knobs
# -------------------------------
DEF_GK_BLEND = 0.18
GK_SHOT_SCALING = 30
SHOOTER_NOISE_MIN = 0.85
SHOOTER_NOISE_MAX = 1.15
GK_NOISE_MIN = 0.92
GK_NOISE_MAX = 1.08

# -------------------------------
# Free Kick (FK) Tuning Knobs
# -------------------------------
AVG_FREE_KICKS_PER_GAME = 10
FREE_KICK_VARIANCE = 5
FK_ZONES = {
    'DEEP':      (0.25, 0.00, 0.05, 1.00),
    'MIDDLE':    (0.50, 0.02, 0.40, 0.90),
    'ATTACKING': (0.17, 0.30, 0.70, 0.75),
    'DANGEROUS': (0.08, 0.85, 0.15, 0.60),
}
FK_SHOT_SCALING = 24
FK_GOAL_CONVERSION_FACTOR_BASE = 0.60

# ---------------------------------------
# Penalty Kick Tuning Knobs (NEW)
# ---------------------------------------
# The 'why': These constants allow for fine-tuning the drama and realism of penalties.
# The base probability of a defensive stop resulting in a penalty kick.
PENALTY_AWARD_PROBABILITY = 0.03
# Dedicated logistic scaling for penalty kicks. A lower value means the skill difference is more impactful.
PENALTY_SCALING = 20
# Global conversion multiplier for penalties. A value > 1.0 reflects the high-pressure, close-range nature of a penalty.
PENALTY_CONVERSION_FACTOR = 1.15


def logistic_probability(strength_a, strength_b, scaling_factor):
    diff = strength_a - strength_b
    try:
        exponent = -diff / scaling_factor
        if exponent > 10: return 0.0
        elif exponent < -10: return 1.0
        else: return 1 / (1 + math.exp(exponent))
    except OverflowError:
        return 1.0 if diff > 0 else 0.0

def goal_probability(shooter_eff: float, keeper_eff: float, scaling=GK_SHOT_SCALING, conversion_factor=GOAL_CONVERSION_FACTOR) -> float:
    rand_shooter = shooter_eff * random.uniform(SHOOTER_NOISE_MIN, SHOOTER_NOISE_MAX)
    rand_keeper = keeper_eff * random.uniform(GK_NOISE_MIN, GK_NOISE_MAX)
    diff = rand_shooter - rand_keeper
    try:
        exponent = -diff / scaling
        if exponent > 10: base = 0.0
        elif exponent < -10: base = 1.0
        else: base = 1 / (1 + math.exp(exponent))
    except OverflowError:
        base = 1.0 if diff > 0 else 0.0
    return min(1.0, base * conversion_factor)

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
        self.best_fk_taker = self._find_best_fk_taker()
        # NEW: Find the best penalty taker on the selected team
        self.best_penalty_taker = self._find_best_penalty_taker()

    def get_starting_11(self):
        return [p for players in self.lineup.values() for p in players]

    def _find_best_fk_taker(self):
        starting_11 = self.get_starting_11()
        if not starting_11: return None
        return max(starting_11, key=lambda p: getattr(p, 'free_kick_ability', 50))

    def _find_best_penalty_taker(self):
        """
        NEW: Finds the player on the pitch with the highest penalty_taking skill.
        The 'why': The team's designated taker is usually the most skilled, not just a random forward.
        """
        starting_11 = self.get_starting_11()
        if not starting_11: return None
        return max(starting_11, key=lambda p: getattr(p, 'penalty_taking', 50))

    def select_lineup(self):
        if self.fixed_lineup_ids:
            fixed_players = [p for p in self.team.players if p.id in self.fixed_lineup_ids]
            self.lineup = {pos: [] for pos in Position}
            for p in fixed_players: self.lineup[p.position].append(p)
        else:
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
            # Updated to include penalty taking ability in lineup data
            'lineup': [{'name': p.name, 'position': p.position.value, 'skill': p.skill, 'shape': p.shape, 'fk_ability': getattr(p, 'free_kick_ability', 50), 'penalty_taking': getattr(p, 'penalty_taking', 50), 'id': p.id} for p in self.get_starting_11()]
        }

class MatchSimulator:
    def __init__(self, team_a_model, team_b_model, logging_enabled=True, fixed_a_ids=None, fixed_b_ids=None, is_knockout=False):
        self.team_a = MatchTeam(team_a_model, is_home=True, fixed_lineup_ids=fixed_a_ids)
        self.team_b = MatchTeam(team_b_model, is_home=False, fixed_lineup_ids=fixed_b_ids)
        self.logging_enabled = logging_enabled
        # NEW: Flag to determine if a shootout should occur on a draw.
        self.is_knockout = is_knockout
        self.log = []
        self.minute = 0
        self.zone = 'M'
        self.possession = random.choice([self.team_a, self.team_b])
        self.free_kick_events = self._generate_free_kicks()
        # NEW: Attributes to store shootout results.
        self.shootout_score_a = 0
        self.shootout_score_b = 0
        self.winner_on_penalties = None

    def _generate_free_kicks(self):
        num_kicks = max(10, int(random.gauss(AVG_FREE_KICKS_PER_GAME, FREE_KICK_VARIANCE)))
        events = []
        zone_names, likelihoods = list(FK_ZONES.keys()), [z[0] for z in FK_ZONES.values()]
        for _ in range(num_kicks):
            events.append({
                'minute': random.randint(1, 90),
                'team': self.team_a if random.random() < 0.5 else self.team_b,
                'zone': random.choices(zone_names, weights=likelihoods, k=1)[0]
            })
        events.sort(key=lambda e: e['minute'])
        return events

    def log_event(self, message, importance='normal', event_type=None, details=None):
        if not self.logging_enabled: return
        self.log.append({'minute': self.minute, 'message': message, 'importance': importance, 'event_type': event_type, 'details': details})

    def simulate(self):
        if len(self.team_a.get_starting_11()) < 11 or len(self.team_b.get_starting_11()) < 11:
            self.log_event("Match abandoned due to insufficient players.", importance='error')
            return self.get_results()

        if self.logging_enabled:
            self.log_event(f"Kickoff! (Total FKs scheduled: {len(self.free_kick_events)})", importance='info')

        while self.minute < 90:
            self._process_scheduled_free_kicks()
            if self.minute >= 90: break
            time_increment = random.randint(1, 6)
            last_minute = self.minute
            self.minute += time_increment
            if self.minute > 90: self.minute = 90
            if self.logging_enabled and last_minute < 45 and self.minute >= 45: self.log_event("Halftime", importance='info')
            self.process_event()

        if self.logging_enabled:
            self.log_event(f"Full Time! Final score: {self.team_a.score} - {self.team_b.score}", importance='final')
        
        # NEW: Resolve shootout if it's a knockout match and the score is tied.
        if self.is_knockout and self.team_a.score == self.team_b.score:
            self.resolve_shootout()
            
        return self.get_results()

    def _process_scheduled_free_kicks(self):
        while self.free_kick_events and self.free_kick_events[0]['minute'] <= self.minute:
            fk_event = self.free_kick_events.pop(0)
            self.minute = fk_event['minute']
            self.resolve_free_kick(fk_event)

    def process_event(self):
        if not self.possession: self.possession = random.choice([self.team_a, self.team_b])
        if self.zone == 'M': self.resolve_midfield_battle()
        elif self.zone == 'A': self.resolve_attack(self.team_a, self.team_b)
        elif self.zone == 'B': self.resolve_attack(self.team_b, self.team_a)
        
    def resolve_free_kick(self, fk_event):
        attacker = fk_event['team']
        defender = self.team_b if attacker == self.team_a else self.team_a
        zone, (_, p_direct, p_indirect_attack, def_mod) = fk_event['zone'], FK_ZONES[fk_event['zone']]
        self.log_event(f"Free Kick to {attacker.team.name} in a {zone.lower()} position.", event_type='FREE_KICK', importance='set_piece')
        action_roll = random.random()
        if action_roll < p_direct:
            self.resolve_direct_free_kick(attacker, defender, zone)
        elif action_roll < (p_direct + p_indirect_attack):
            self.log_event(f"{attacker.team.name} sends a cross or pass into the attacking zone.", event_type='INDIRECT_FK_ATTACK')
            self.possession = attacker
            self.zone = 'A' if attacker == self.team_a else 'B'
            self.resolve_attack(attacker, defender, defense_modifier=def_mod)
        else:
            self.log_event(f"{attacker.team.name} restarts play safely.", event_type='FK_RESTART', importance='minor')
            self.possession = attacker
            self.zone = 'M'

    def resolve_direct_free_kick(self, attacker, defender, zone):
        taker, goalkeeper = attacker.best_fk_taker, defender.get_goalkeeper()
        if not taker or not goalkeeper: return
        self.log_event(f"{taker.name} steps up to take the direct free kick.", importance='high', event_type='DIRECT_FK')
        dist_factor = {'DANGEROUS': 1.3, 'ATTACKING': 0.8, 'MIDDLE': 0.3}.get(zone, 0.1)
        final_conv_factor = FK_GOAL_CONVERSION_FACTOR_BASE * dist_factor
        prob = goal_probability(taker.effective_fk_ability, goalkeeper.effective_skill, scaling=FK_SHOT_SCALING, conversion_factor=final_conv_factor)
        roll = random.random()
        if roll < prob:
            attacker.score += 1
            if self.logging_enabled:
                details = f"Direct FK ({zone}): {taker.name} (Eff FK: {taker.effective_fk_ability:.1f}) vs {goalkeeper.name} (Eff GK: {goalkeeper.effective_skill:.1f})\n- Prob: {prob:.1%}, Roll: {roll:.3f} -> GOAL"
                self.log_event(f"GOAL! {taker.name}! ({self.team_a.score}-{self.team_b.score})", importance='goal', event_type='GOAL_FK', details=details)
            self.possession = defender
            self.zone = 'M'
        else:
            if self.logging_enabled:
                details = f"Direct FK ({zone}): {taker.name} (Eff FK: {taker.effective_fk_ability:.1f}) vs {goalkeeper.name} (Eff GK: {goalkeeper.effective_skill:.1f})\n- Prob: {prob:.1%}, Roll: {roll:.3f} -> NO GOAL"
                self.log_event(f"NO GOAL! The free kick is saved or missed.", importance='miss', event_type='MISS_FK', details=details)
            self.possession = defender
            self.zone = 'M'
            
    def resolve_midfield_battle(self):
        attacker, defender = (self.possession, self.team_b) if self.possession == self.team_a else (self.possession, self.team_a)
        att_str, def_str = attacker.zonal_strength[Position.MIDFIELDER], defender.zonal_strength[Position.MIDFIELDER]
        prob, roll = logistic_probability(att_str, def_str, MIDFIELD_SCALING), random.random()
        if roll < prob:
            self.zone = 'A' if attacker == self.team_a else 'B'
            if self.logging_enabled: self.log_event(f"{attacker.team.name} advances.")
        else:
            self.possession = defender
            if self.logging_enabled: self.log_event(f"{defender.team.name} wins the ball.")
            
    def resolve_attack(self, attacker, defender, defense_modifier=1.0):
        att_str = attacker.zonal_strength[Position.FORWARD]
        pure_def, gk_str = defender.zonal_strength[Position.DEFENDER], defender.zonal_strength[Position.GOALKEEPER]
        def_gate = ((1.0 - DEF_GK_BLEND) * pure_def + DEF_GK_BLEND * gk_str) * defense_modifier
        prob, roll = logistic_probability(att_str, def_gate, ATTACK_SCALING), random.random()
        if roll < prob:
            if self.logging_enabled: self.log_event(f"{attacker.team.name} creates a chance!", event_type='SHOT_OPPORTUNITY')
            self.resolve_shot(attacker, defender)
        else:
            # NEW: Check for a penalty kick on a defensive stop
            if random.random() < PENALTY_AWARD_PROBABILITY:
                self.log_event(f"PENALTY to {attacker.team.name}!", event_type='PENALTY_AWARDED', importance='high')
                self.resolve_penalty_kick(attacker, defender)
            else:
                self.possession = defender
                self.zone = 'M'
                if self.logging_enabled: self.log_event(f"{defender.team.name}'s defense holds firm.", event_type='DEFENSIVE_STOP')

    def resolve_shot(self, attacker, defender):
        shooter, goalkeeper = attacker.get_random_player([Position.FORWARD, Position.MIDFIELDER]), defender.get_goalkeeper()
        if not shooter or not goalkeeper:
            self.possession, self.zone = defender, 'M'
            return
        prob, roll = goal_probability(shooter.effective_skill, goalkeeper.effective_skill), random.random()
        if roll < prob:
            attacker.score += 1
            if self.logging_enabled:
                details = f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n- Prob: {prob:.1%}, Roll: {roll:.3f} -> GOAL"
                self.log_event(f"GOAL! {shooter.name}! ({self.team_a.score}-{self.team_b.score})", importance='goal', event_type='GOAL', details=details)
        else:
            if self.logging_enabled:
                details = f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n- Prob: {prob:.1%}, Roll: {roll:.3f} -> NO GOAL"
                self.log_event(f"NO GOAL! Shot by {shooter.name}.", importance='miss', event_type='MISS', details=details)
        self.possession, self.zone = defender, 'M'

    def resolve_penalty_kick(self, attacker, defender, taker=None, is_shootout_kick=False):
        """
        NEW: Resolves a single penalty kick, for both in-game and shootout scenarios.
        The 'why': This modular function centralizes penalty logic, ensuring consistency and adhering to DRY.
        It returns a boolean for goal/miss, which is used by the shootout logic to track score.
        """
        if taker is None: taker = attacker.best_penalty_taker
        goalkeeper = defender.get_goalkeeper()
        if not taker or not goalkeeper: return False
        
        prob, roll = goal_probability(taker.effective_penalty_taking, goalkeeper.effective_penalty_saving, scaling=PENALTY_SCALING, conversion_factor=PENALTY_CONVERSION_FACTOR), random.random()
        is_goal = roll < prob

        if self.logging_enabled:
            details = (f"Penalty: {taker.name} (Eff Pen: {taker.effective_penalty_taking:.1f}) vs {goalkeeper.name} (Eff Save: {goalkeeper.effective_penalty_saving:.1f})\n"
                       f"- Pen Scaling: {PENALTY_SCALING}, Conv Factor: {PENALTY_CONVERSION_FACTOR:.2f}\n"
                       f"- Prob: {prob:.1%}, Roll: {roll:.3f} -> {'GOAL' if is_goal else 'NO GOAL'}")
            if is_shootout_kick:
                msg = f"GOAL! {taker.name} scores." if is_goal else f"SAVED! {goalkeeper.name} denies {taker.name}!"
                self.log_event(msg, importance='high', event_type='SHOOTOUT_KICK', details=details)
            else:
                if is_goal: self.log_event(f"GOAL! {taker.name} converts! ({self.team_a.score+1 if attacker == self.team_a else self.team_a.score}-{self.team_b.score+1 if attacker == self.team_b else self.team_b.score})", importance='goal', event_type='GOAL_PENALTY', details=details)
                else: self.log_event(f"MISSED! {taker.name}'s penalty is saved or wide!", importance='miss', event_type='MISS_PENALTY', details=details)
        
        if not is_shootout_kick:
            if is_goal: attacker.score += 1
            self.possession, self.zone = defender, 'M' # Possession resets after in-game penalty

        return is_goal

    def resolve_shootout(self):
        """
        NEW: Manages a full penalty shootout tiebreaker.
        The 'why': This encapsulates the entire shootout flow, from selecting takers to handling
        sudden death, providing a dramatic conclusion to knockout matches.
        """
        self.log_event("The match is drawn. A penalty shootout will decide the winner!", importance='final', event_type='SHOOTOUT_START')
        team_a_players = [p for p in self.team_a.get_starting_11() if p.position != Position.GOALKEEPER]
        team_b_players = [p for p in self.team_b.get_starting_11() if p.position != Position.GOALKEEPER]
        team_a_takers = sorted(team_a_players, key=lambda p: p.penalty_taking, reverse=True)[:5]
        team_b_takers = sorted(team_b_players, key=lambda p: p.penalty_taking, reverse=True)[:5]
        
        for i in range(5):
            self.log_event(f"--- Shootout Round {i+1} ---", importance='info')
            if self.resolve_penalty_kick(self.team_a, self.team_b, taker=team_a_takers[i], is_shootout_kick=True): self.shootout_score_a += 1
            if self.shootout_score_a > self.shootout_score_b + (5 - i) or self.shootout_score_b > self.shootout_score_a + (4 - i): break
            if self.resolve_penalty_kick(self.team_b, self.team_a, taker=team_b_takers[i], is_shootout_kick=True): self.shootout_score_b += 1
            self.log_event(f"Score: {self.team_a.team.name} {self.shootout_score_a} - {self.shootout_score_b} {self.team_b.team.name}", importance='info')
            if self.shootout_score_a > self.shootout_score_b + (4 - i) or self.shootout_score_b > self.shootout_score_a + (4 - i): break
        
        if self.shootout_score_a == self.shootout_score_b:
            self.log_event("--- Sudden Death ---", importance='info')
            rem_a = [p for p in team_a_players if p not in team_a_takers] or team_a_takers
            rem_b = [p for p in team_b_players if p not in team_b_takers] or team_b_takers
            round_num = 0
            while self.shootout_score_a == self.shootout_score_b:
                self.log_event(f"--- Sudden Death Round {round_num + 1} ---", importance='info')
                goal_a = self.resolve_penalty_kick(self.team_a, self.team_b, taker=rem_a[round_num % len(rem_a)], is_shootout_kick=True)
                goal_b = self.resolve_penalty_kick(self.team_b, self.team_a, taker=rem_b[round_num % len(rem_b)], is_shootout_kick=True)
                if goal_a: self.shootout_score_a += 1
                if goal_b: self.shootout_score_b += 1
                self.log_event(f"Score: {self.team_a.team.name} {self.shootout_score_a} - {self.shootout_score_b} {self.team_b.team.name}", importance='info')
                round_num += 1

        self.winner_on_penalties = self.team_a.team.name if self.shootout_score_a > self.shootout_score_b else self.team_b.team.name
        self.log_event(f"{self.winner_on_penalties} wins the shootout {self.shootout_score_a}-{self.shootout_score_b}!", importance='final', event_type='SHOOTOUT_END')

    def get_results(self):
        return {
            'log': self.log,
            'score_a': self.team_a.score,
            'score_b': self.team_b.score,
            'team_a_name': self.team_a.team.name,
            'team_b_name': self.team_b.team.name,
            # NEW: Shootout results are included in the final dictionary.
            'shootout_score_a': self.shootout_score_a,
            'shootout_score_b': self.shootout_score_b,
            'winner_on_penalties': self.winner_on_penalties,
        }

def simulate_match(team_a_id, team_b_id, is_knockout=False):
    """ Helper to run a single, fully-logged match. Now accepts is_knockout flag. """
    team_a, team_b = Team.query.get(team_a_id), Team.query.get(team_b_id)
    if not team_a or not team_b:
        return {'log': [{'message': 'Invalid Teams'}], 'score_a': 0, 'score_b': 0, 'team_a_name': '?', 'team_b_name': '?'}
    return MatchSimulator(team_a, team_b, logging_enabled=True, is_knockout=is_knockout).simulate()

def get_prematch_odds(user_team_id=None, enemy_team_id=None, simulations=100, user_team_model=None, enemy_team_model=None, fixed_user_lineup_ids=None):
    """ Helper to run many non-logged simulations for statistical analysis. """
    if not user_team_model and user_team_id: user_team_model = Team.query.get(user_team_id)
    if not enemy_team_model and enemy_team_id: enemy_team_model = Team.query.get(enemy_team_id)
    if not user_team_model or not enemy_team_model: return {'error': 'Invalid teams'}

    user_team_home = MatchTeam(user_team_model, is_home=True, fixed_lineup_ids=fixed_user_lineup_ids)
    user_team_away = MatchTeam(user_team_model, is_home=False, fixed_lineup_ids=fixed_user_lineup_ids)
    enemy_team_home = MatchTeam(enemy_team_model, is_home=True)
    enemy_team_away = MatchTeam(enemy_team_model, is_home=False)

    def _run_fixture_sims(home_team_model, away_team_model, fixed_home_ids=None, fixed_away_ids=None):
        wins, draws, losses, goals_for, goals_against = 0, 0, 0, 0, 0
        for _ in range(simulations):
            # NEW: is_knockout is explicitly False. Odds calculation is only for 90-minute results.
            simulator = MatchSimulator(home_team_model, away_team_model, logging_enabled=False, fixed_a_ids=fixed_home_ids, fixed_b_ids=fixed_away_ids, is_knockout=False)
            result = simulator.simulate()
            goals_for, goals_against = goals_for + result['score_a'], goals_against + result['score_b']
            if result['score_a'] > result['score_b']: wins += 1
            elif result['score_b'] > result['score_a']: losses += 1
            else: draws += 1
        return {'win_prob': (wins/simulations)*100, 'draw_prob': (draws/simulations)*100, 'loss_prob': (losses/simulations)*100, 'avg_goals_for': goals_for/simulations, 'avg_goals_against': goals_against/simulations}

    home_fixture_probs = _run_fixture_sims(user_team_model, enemy_team_model, fixed_home_ids=fixed_user_lineup_ids)
    away_fixture_probs = _run_fixture_sims(enemy_team_model, user_team_model, fixed_away_ids=fixed_user_lineup_ids)

    return {
        'home_fixture': {'probs': home_fixture_probs, 'stats': {'user_team': user_team_home.get_stats_dict(), 'enemy_team': enemy_team_away.get_stats_dict()}},
        'away_fixture': {'probs': away_fixture_probs, 'stats': {'user_team': user_team_away.get_stats_dict(), 'enemy_team': enemy_team_home.get_stats_dict()}},
        'simulations_run': simulations
    }
