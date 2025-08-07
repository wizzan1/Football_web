import random
import math
from textfootball.models import Team, Player, Position, Personality
from textfootball import db # We need db access to commit morale changes

# ===========================
# Configuration / Tunables
# ===========================

# Formation
FORMATION = {
    Position.GOALKEEPER: 1,
    Position.DEFENDER: 4,
    Position.MIDFIELDER: 4,
    Position.FORWARD: 2
}

# Home advantage
HOME_ADVANTAGE_BOOST = 1.03

# Flow & scoring
MIDFIELD_SCALING = 32
ATTACK_SCALING = 32
GOAL_CONVERSION_FACTOR_BASE = 1.0

# Shot Distance parameters
SHOT_DISTANCE_MIN = 5   # Meters
SHOT_DISTANCE_MAX = 35  # Meters
OPTIMAL_SHOT_DISTANCE = 12
DISTANCE_PENALTY_FACTOR = 0.03

# Goalkeeper-specific
DEF_GK_BLEND = 0.18
GK_SHOT_SCALING = 30
SHOOTER_NOISE_MIN = 0.85
SHOOTER_NOISE_MAX = 1.15
GK_NOISE_MIN = 0.92
GK_NOISE_MAX = 1.08

# Free Kick (FK) Tuning Knobs
AVG_FREE_KICKS_PER_GAME = 0
FREE_KICK_VARIANCE = 0
FK_ZONES = {
    'DEEP':      (0.25, 0.00, 0.05, 1.00),
    'MIDDLE':    (0.50, 0.02, 0.40, 0.90),
    'ATTACKING': (0.17, 0.30, 0.70, 0.75),
    'DANGEROUS': (0.08, 0.85, 0.15, 0.60),
}
FK_SHOT_SCALING = 24
FK_GOAL_CONVERSION_FACTOR_BASE = 0.60

# Penalty Kick Tuning Knobs
PENALTY_AWARD_PROBABILITY = 0.03
PENALTY_SCALING = 20
PENALTY_CONVERSION_FACTOR = 1.15

# ---------------------------------------
# Morale System Tuning Knobs
# ---------------------------------------
MORALE_BASE_WIN = 8
MORALE_BASE_LOSS = -10
MORALE_BASE_DRAW = 1
MORALE_MARGIN_THRESHOLD = 3
MORALE_MARGIN_MULTIPLIER = 1.5
MORALE_GOAL_BONUS = 3
MORALE_HAT_TRICK_BONUS = 10
MORALE_DRIFT_TARGET = 75
MORALE_DRIFT_RATE = 0.05
MORALE_EFFECT_ACTIVE = 0

def logistic_probability(strength_a, strength_b, scaling_factor):
    diff = strength_a - strength_b
    try:
        exponent = -diff / scaling_factor
        if exponent > 10: return 0.0
        elif exponent < -10: return 1.0
        else: return 1 / (1 + math.exp(exponent))
    except OverflowError:
        return 1.0 if diff > 0 else 0.0

def goal_probability(shooter_eff: float, keeper_eff: float, scaling=GK_SHOT_SCALING, base_conversion_factor=GOAL_CONVERSION_FACTOR_BASE, distance=None) -> float:
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

    if distance is not None:
        if distance < OPTIMAL_SHOT_DISTANCE:
            distance_modifier = min(1.1, 1.0 + (OPTIMAL_SHOT_DISTANCE - distance) * 0.01)
        else:
            penalty = (distance - OPTIMAL_SHOT_DISTANCE) * DISTANCE_PENALTY_FACTOR
            distance_modifier = max(0.1, 1.0 - penalty)
        final_conversion_factor = base_conversion_factor * distance_modifier
    else:
        final_conversion_factor = base_conversion_factor

    return min(1.0, base * final_conversion_factor)

class MatchTeam:
    def __init__(self, team_model, is_home=False, fixed_lineup_ids=None):
        self.team = team_model
        self.color = team_model.color if team_model else '#cccccc'
        self.is_home = is_home
        self.fixed_lineup_ids = fixed_lineup_ids
        self.lineup = {}
        self.base_zonal_strength = {}
        self.zonal_strength = {}
        self.avg_shape = 0
        self.avg_base_skill = 0
        self.avg_effective_skill = 0
        self.avg_morale = 0
        self.score = 0
        self.player_stats = {}
        self.match_stats = {
            'possession_time': 0,
            'shots': 0,
            'passes_won': 0,
            'tackles_won': 0,
            'territorial_advantage_time': 0
        }

        self.select_lineup()
        self.calculate_zonal_strength()
        self.best_fk_taker = self._find_best_fk_taker()
        self.best_penalty_taker = self._find_best_penalty_taker()
        self._initialize_player_stats()

    def _initialize_player_stats(self):
        for player in self.team.players:
            self.player_stats[player.id] = {'goals': 0}

    def record_goal(self, player):
        if player and player.id in self.player_stats:
            self.player_stats[player.id]['goals'] += 1

    def record_stat(self, stat_name, amount=1):
        if stat_name in self.match_stats:
            self.match_stats[stat_name] += amount

    def get_starting_11(self):
        return [p for players in self.lineup.values() for p in players]

    def _find_best_fk_taker(self):
        starting_11 = self.get_starting_11()
        if not starting_11: return None
        return max(starting_11, key=lambda p: getattr(p, 'free_kick_ability', 50))

    def _find_best_penalty_taker(self):
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
            self.avg_morale = sum(p.morale for p in starting_11) / len(starting_11)

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
            'color': self.color,
            'avg_base_skill': self.avg_base_skill, 'avg_shape': self.avg_shape, 'avg_effective_skill': self.avg_effective_skill,
            'avg_morale': self.avg_morale,
            'base_zonal_strength': {pos.name: strength for pos, strength in self.base_zonal_strength.items()},
            'zonal_strength': {pos.name: strength for pos, strength in self.zonal_strength.items()},
            'lineup': [{'name': p.name, 'position': p.position.value, 'skill': p.skill, 'shape': p.shape, 'morale': p.morale, 'personality': p.personality.value, 'fk_ability': getattr(p, 'free_kick_ability', 50), 'penalty_taking': getattr(p, 'penalty_taking', 50), 'id': p.id} for p in self.get_starting_11()]
        }

class MatchSimulator:
    def __init__(self, team_a_model, team_b_model, logging_enabled=True, fixed_a_ids=None, fixed_b_ids=None, is_knockout=False, morale_params=None):
        self.morale_params = self._get_morale_params(morale_params)
        self.team_a = MatchTeam(team_a_model, is_home=True, fixed_lineup_ids=fixed_a_ids) if team_a_model else None
        self.team_b = MatchTeam(team_b_model, is_home=False, fixed_lineup_ids=fixed_b_ids) if team_b_model else None
        self.logging_enabled = logging_enabled
        self.is_knockout = is_knockout
        self.log = []
        self.minute = 0
        self.zone = 'M'
        self.dominance_score = 0.0

        if self.team_a and self.team_b:
            self.possession = random.choice([self.team_a, self.team_b])
            self.free_kick_events = self._generate_free_kicks()
        else:
            self.possession = None
            self.free_kick_events = []

        self.shootout_score_a = 0
        self.shootout_score_b = 0
        self.winner_on_penalties = None
        self.commit_changes = False

    def _get_morale_params(self, overrides):
        params = {
            'MORALE_BASE_WIN': MORALE_BASE_WIN,
            'MORALE_BASE_LOSS': MORALE_BASE_LOSS,
            'MORALE_BASE_DRAW': MORALE_BASE_DRAW,
            'MORALE_MARGIN_THRESHOLD': MORALE_MARGIN_THRESHOLD,
            'MORALE_MARGIN_MULTIPLIER': MORALE_MARGIN_MULTIPLIER,
            'MORALE_GOAL_BONUS': MORALE_GOAL_BONUS,
            'MORALE_HAT_TRICK_BONUS': MORALE_HAT_TRICK_BONUS,
            'MORALE_DRIFT_TARGET': MORALE_DRIFT_TARGET,
            'MORALE_DRIFT_RATE': MORALE_DRIFT_RATE,
        }
        if overrides:
            params.update(overrides)
        return params

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

    def log_event(self, message, importance='normal', event_type=None, details=None, metadata=None):
        if not self.logging_enabled: return
        event_metadata = metadata if metadata is not None else {}
        event_metadata['dominance'] = round(self.dominance_score, 3)

        self.log.append({
            'minute': self.minute,
            'message': message,
            'importance': importance,
            'event_type': event_type,
            'details': details,
            'metadata': event_metadata
        })

    def simulate(self, commit_changes=False):
        self.commit_changes = commit_changes

        if not self.team_a or not self.team_b:
            self.log_event("Match abandoned due to missing team models.", importance='error')
            return self.get_results()

        if len(self.team_a.get_starting_11()) < 11 or len(self.team_b.get_starting_11()) < 11:
            self.log_event("Match abandoned due to insufficient players.", importance='error')
            return self.get_results()

        if self.logging_enabled:
            self.log_event(f"Kickoff! (Total FKs scheduled: {len(self.free_kick_events)})", importance='info')

        while self.minute < 90:
            self._process_scheduled_free_kicks()
            if self.minute >= 90: break
            time_increment = random.randint(1, 6)

            if self.possession:
                self.possession.record_stat('possession_time', time_increment)
                if (self.possession == self.team_a and self.zone == 'A') or \
                   (self.possession == self.team_b and self.zone == 'B'):
                    self.possession.record_stat('territorial_advantage_time', time_increment)

            last_minute = self.minute
            self.minute += time_increment
            if self.minute > 90: self.minute = 90

            self.calculate_dominance()

            if self.logging_enabled and last_minute < 45 and self.minute >= 45: self.log_event("Halftime", importance='info')
            self.process_event()

        if self.logging_enabled:
            self.log_event(f"Full Time! Final score: {self.team_a.score} - {self.team_b.score}", importance='final')

        if self.is_knockout and self.team_a.score == self.team_b.score:
            self.resolve_shootout()

        if MORALE_EFFECT_ACTIVE == 1:
            self.apply_post_match_morale_updates()

        return self.get_results()

    def calculate_dominance(self):
        W_POSSESSION = 0.3
        W_TERRITORY = 0.3
        W_ACTIONS = 0.4

        total_time = self.team_a.match_stats['possession_time'] + self.team_b.match_stats['possession_time']
        if total_time == 0:
            return

        poss_a = self.team_a.match_stats['possession_time'] / total_time
        poss_b = self.team_b.match_stats['possession_time'] / total_time
        score_possession = poss_b - poss_a

        terr_a = self.team_a.match_stats['territorial_advantage_time'] / total_time
        terr_b = self.team_b.match_stats['territorial_advantage_time'] / total_time
        score_territory = terr_b - terr_a

        actions_a = self.team_a.match_stats['passes_won'] + self.team_a.match_stats['tackles_won'] + self.team_a.match_stats['shots'] * 3
        actions_b = self.team_b.match_stats['passes_won'] + self.team_b.match_stats['tackles_won'] + self.team_b.match_stats['shots'] * 3
        total_actions = actions_a + actions_b
        if total_actions > 0:
            score_actions = (actions_b - actions_a) / total_actions
        else:
            score_actions = 0

        calculated_score = (score_possession * W_POSSESSION +
                            score_territory * W_TERRITORY +
                            score_actions * W_ACTIONS)

        MOMENTUM_FACTOR = 0.1
        self.dominance_score += (calculated_score - self.dominance_score) * MOMENTUM_FACTOR
        self.dominance_score = max(-1.0, min(1.0, self.dominance_score))

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
            attacker.record_stat('passes_won')
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

        attacker.record_stat('shots')

        self.log_event(f"{taker.name} steps up to take the direct free kick.", importance='high', event_type='DIRECT_FK')
        dist_factor = {'DANGEROUS': 1.3, 'ATTACKING': 0.8, 'MIDDLE': 0.3}.get(zone, 0.1)
        final_conv_factor = FK_GOAL_CONVERSION_FACTOR_BASE * dist_factor
        prob = goal_probability(taker.effective_fk_ability, goalkeeper.effective_skill, scaling=FK_SHOT_SCALING, base_conversion_factor=final_conv_factor)
        roll = random.random()
        if roll < prob:
            attacker.score += 1
            attacker.record_goal(taker)
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
            attacker.record_stat('passes_won')
            self.zone = 'A' if attacker == self.team_a else 'B'
            if self.logging_enabled: self.log_event(f"{attacker.team.name} advances.")
        else:
            defender.record_stat('tackles_won')
            self.possession = defender
            if self.logging_enabled: self.log_event(f"{defender.team.name} wins the ball.")

    def resolve_attack(self, attacker, defender, defense_modifier=1.0):
        att_str = attacker.zonal_strength[Position.FORWARD]
        pure_def, gk_str = defender.zonal_strength[Position.DEFENDER], defender.zonal_strength[Position.GOALKEEPER]
        def_gate = ((1.0 - DEF_GK_BLEND) * pure_def + DEF_GK_BLEND * gk_str) * defense_modifier
        prob, roll = logistic_probability(att_str, def_gate, ATTACK_SCALING), random.random()
        if roll < prob:
            self.resolve_shot(attacker, defender)
        else:
            if random.random() < PENALTY_AWARD_PROBABILITY:
                self.log_event(f"PENALTY to {attacker.team.name}!", event_type='PENALTY_AWARDED', importance='high')
                self.resolve_penalty_kick(attacker, defender)
            else:
                defender.record_stat('tackles_won')
                self.possession = defender
                self.zone = 'M'
                if self.logging_enabled: self.log_event(f"{defender.team.name}'s defense holds firm.", event_type='DEFENSIVE_STOP')

    def resolve_shot(self, attacker, defender):
        shooter, goalkeeper = attacker.get_random_player([Position.FORWARD, Position.MIDFIELDER]), defender.get_goalkeeper()
        if not shooter or not goalkeeper:
            self.possession, self.zone = defender, 'M'
            return

        attacker.record_stat('shots')

        distance = random.uniform(SHOT_DISTANCE_MIN, SHOT_DISTANCE_MAX)
        prob, roll = goal_probability(shooter.effective_skill, goalkeeper.effective_skill, distance=distance), random.random()

        if prob > 0.65: danger_level = "Critical"
        elif prob > 0.45: danger_level = "High"
        elif prob > 0.25: danger_level = "Medium"
        else: danger_level = "Low"

        if self.logging_enabled:
            pre_shot_msg = f"{shooter.name} is taking a shot!"
            metadata = {
                'distance': f"{distance:.1f}m",
                'danger_level': danger_level
            }
            self.log_event(pre_shot_msg, importance='pre_shot', event_type='SHOT_INITIATED', metadata=metadata)

        if roll < prob:
            attacker.score += 1
            attacker.record_goal(shooter)
            if self.logging_enabled:
                details = f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n- Dist: {distance:.1f}m, Prob: {prob:.1%}, Roll: {roll:.3f} -> GOAL"
                self.log_event(f"GOAL! {shooter.name}! ({self.team_a.score}-{self.team_b.score})", importance='goal', event_type='GOAL', details=details)
        else:
            if self.logging_enabled:
                details = f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n- Dist: {distance:.1f}m, Prob: {prob:.1%}, Roll: {roll:.3f} -> NO GOAL"
                if prob - roll < 0.1:
                    outcome_msg = f"WHAT A SAVE by {goalkeeper.name}!"
                    importance = 'save'
                else:
                    outcome_msg = f"JUST WIDE! Shot by {shooter.name}."
                    importance = 'miss'
                self.log_event(outcome_msg, importance=importance, event_type='MISS', details=details)

        self.possession, self.zone = defender, 'M'

    def resolve_penalty_kick(self, attacker, defender, taker=None, is_shootout_kick=False):
        if taker is None: taker = attacker.best_penalty_taker
        goalkeeper = defender.get_goalkeeper()
        if not taker or not goalkeeper: return False

        if not is_shootout_kick:
            attacker.record_stat('shots')

        prob, roll = goal_probability(taker.effective_penalty_taking, goalkeeper.effective_penalty_saving, scaling=PENALTY_SCALING, base_conversion_factor=PENALTY_CONVERSION_FACTOR), random.random()
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
            if is_goal:
                attacker.score += 1
                attacker.record_goal(taker)
            self.possession, self.zone = defender, 'M'

        return is_goal

    def resolve_shootout(self):
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

    def apply_post_match_morale_updates(self):
        score_a, score_b = self.team_a.score, self.team_b.score

        if self.winner_on_penalties:
            result_a = 'WIN' if self.winner_on_penalties == self.team_a.team.name else 'LOSS'
            result_b = 'LOSS' if result_a == 'WIN' else 'WIN'
            margin_a = margin_b = 0
        elif score_a > score_b:
            result_a, result_b = 'WIN', 'LOSS'
            margin_a, margin_b = score_a - score_b, score_b - score_a
        elif score_b > score_a:
            result_a, result_b = 'LOSS', 'WIN'
            margin_a, margin_b = score_a - score_b, score_b - score_a
        else:
            result_a = result_b = 'DRAW'
            margin_a = margin_b = 0

        self._process_team_morale(self.team_a, result_a, margin_a)
        self._process_team_morale(self.team_b, result_b, margin_b)

        if self.commit_changes:
            try:
                db.session.commit()
                self.log_event("Post-match morale updates committed to database.", importance='system')
            except Exception as e:
                db.session.rollback()
                self.log_event(f"Error committing morale updates: {e}", importance='error', event_type='DB_ERROR')

    def _process_team_morale(self, match_team, result, margin):
        params = self.morale_params

        if result == 'WIN':
            base_change = params['MORALE_BASE_WIN']
            is_positive = True
            is_significant = margin >= params['MORALE_MARGIN_THRESHOLD']
        elif result == 'LOSS':
            base_change = params['MORALE_BASE_LOSS']
            is_positive = False
            is_significant = abs(margin) >= params['MORALE_MARGIN_THRESHOLD']
        else: # DRAW
            base_change = params['MORALE_BASE_DRAW']
            is_positive = match_team.avg_morale < params['MORALE_DRIFT_TARGET']
            is_significant = False

        margin_multiplier = params['MORALE_MARGIN_MULTIPLIER'] if is_significant else 1.0
        starting_11_ids = {p.id for p in match_team.get_starting_11()}

        for player in match_team.team.players:
            outcome_change = 0
            if player.id in starting_11_ids:
                personality_multiplier = player.get_personality_multiplier(is_positive)
                outcome_change = base_change * margin_multiplier * personality_multiplier

            performance_change = 0
            goals_scored = match_team.player_stats[player.id]['goals']
            if goals_scored >= 3:
                performance_change = params['MORALE_HAT_TRICK_BONUS']
            elif goals_scored > 0:
                performance_change = goals_scored * params['MORALE_GOAL_BONUS']

            drift_change = 0
            if player.id not in starting_11_ids:
                distance_to_target = params['MORALE_DRIFT_TARGET'] - player.morale
                drift_change = distance_to_target * params['MORALE_DRIFT_RATE']

            total_change = int(round(outcome_change + performance_change + drift_change))
            new_morale = max(0, min(100, player.morale + total_change))
            old_morale = player.morale
            player.morale = new_morale

            if self.logging_enabled and abs(total_change) > 0:
                log_details = (f"Player: {player.name} ({player.personality.value}), Result: {result} (Margin {margin}), "
                               f"Goals: {goals_scored}.\n"
                               f"Changes -> Outcome: {outcome_change:.1f}, Performance: {performance_change:.1f}, Drift: {drift_change:.1f}.\n"
                               f"Total: {total_change}. Morale: {old_morale} -> {player.morale}")
                self.log_event(f"{player.name} morale change: {total_change:+d}", importance='minor', event_type='MORALE_UPDATE', details=log_details)

    def get_results(self):
        return {
            'log': self.log,
            'score_a': self.team_a.score if self.team_a else 0,
            'score_b': self.team_b.score if self.team_b else 0,
            'team_a_name': self.team_a.team.name if self.team_a else 'N/A',
            'team_b_name': self.team_b.team.name if self.team_b else 'N/A',
            'team_a_color': self.team_a.color if self.team_a else '#cccccc',
            'team_b_color': self.team_b.color if self.team_b else '#cccccc',
            'shootout_score_a': self.shootout_score_a,
            'shootout_score_b': self.shootout_score_b,
            'winner_on_penalties': self.winner_on_penalties,
        }

def simulate_match(team_a_id, team_b_id, is_knockout=False):
    team_a, team_b = Team.query.get(team_a_id), Team.query.get(team_b_id)
    if not team_a or not team_b:
        return {'log': [{'message': 'Invalid Teams'}], 'score_a': 0, 'score_b': 0, 'team_a_name': '?', 'team_b_name': '?'}

    simulator = MatchSimulator(team_a, team_b, logging_enabled=True, is_knockout=is_knockout)
    return simulator.simulate(commit_changes=True)

def get_prematch_odds(user_team_id=None, enemy_team_id=None, simulations=100, user_team_model=None, enemy_team_model=None, fixed_user_lineup_ids=None, morale_params=None):
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
            simulator = MatchSimulator(
                home_team_model,
                away_team_model,
                logging_enabled=False,
                fixed_a_ids=fixed_home_ids,
                fixed_b_ids=fixed_away_ids,
                is_knockout=False,
                morale_params=morale_params
            )
            result = simulator.simulate(commit_changes=False)

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
