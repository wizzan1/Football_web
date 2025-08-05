# app/match_sim.py
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
HOME_ADVANTAGE_BOOST = 1.03 # 3% boost to home team strengths
# Scaling factors
MIDFIELD_SCALING = 30
ATTACK_SCALING = 25
SHOT_SCALING = 20
GOAL_CONVERSION_FACTOR = 0.45
def logistic_probability(strength_a, strength_b, scaling_factor):
    rand_a = strength_a * random.uniform(0.85, 1.15)
    rand_b = strength_b * random.uniform(0.85, 1.15)
    diff = rand_a - rand_b
    try:
        if diff / scaling_factor < -10: return 0.0
        elif diff / scaling_factor > 10: return 1.0
        else: return 1 / (1 + math.exp(-diff / scaling_factor))
    except OverflowError:
        return 1.0 if diff > 0 else 0.0
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
            base_strength = sum(p.effective_skill for p in players) / len(players) if players else 10
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
        if not self.logging_enabled: return
        self.log.append({'minute': self.minute, 'message': message, 'importance': importance, 'event_type': event_type, 'details': details})
    def simulate(self):
        if len(self.team_a.get_starting_11()) < 11 or len(self.team_b.get_starting_11()) < 11:
            self.log_event("Match abandoned due to insufficient players.", importance='error')
            return self.get_results()
        if self.logging_enabled: self.log_event(f"Kickoff!", importance='info')
        while self.minute < 90:
            time_increment = random.randint(1, 5)
            last_minute = self.minute
            self.minute += time_increment
            if self.minute > 90: self.minute = 90
            if self.logging_enabled and last_minute < 45 and self.minute >= 45:
                   self.log_event("Halftime", importance='info')
            self.process_event()
        if self.logging_enabled: self.log_event(f"Full Time! Final score: {self.team_a.score} - {self.team_b.score}", importance='final')
        return self.get_results()
    def process_event(self):
        if self.zone == 'M': self.resolve_midfield_battle()
        elif self.zone == 'A': self.resolve_attack(self.team_a, self.team_b)
        elif self.zone == 'B': self.resolve_attack(self.team_b, self.team_a)
    def resolve_midfield_battle(self):
        attacker, defender = (self.possession, self.team_b) if self.possession == self.team_a else (self.possession, self.team_a)
        att_str, def_str = attacker.zonal_strength[Position.MIDFIELDER], defender.zonal_strength[Position.MIDFIELDER]
        prob = logistic_probability(att_str, def_str, MIDFIELD_SCALING)
        roll = random.random()
        if roll < prob:
            self.zone = 'A' if attacker == self.team_a else 'B'
            result_text = "Success"
        else:
            self.possession = defender
            result_text = "Fail"
        if self.logging_enabled:
            att_d = f"{attacker.base_zonal_strength[Position.MIDFIELDER]:.1f} * {HOME_ADVANTAGE_BOOST} (H) -> {att_str:.1f}" if attacker.is_home else f"{att_str:.1f}"
            def_d = f"{defender.base_zonal_strength[Position.MIDFIELDER]:.1f} * {HOME_ADVANTAGE_BOOST} (H) -> {def_str:.1f}" if defender.is_home else f"{def_str:.1f}"
            details = (f"Midfield: {attacker.team.name} vs {defender.team.name}\n- Att Str: {att_d}\n- Def Str: {def_d}\n- Prob to Advance: {prob:.1%}\n- Roll: {roll:.3f} -> {result_text}")
            message = f"{attacker.team.name} advances." if result_text == "Success" else f"{defender.team.name} wins the ball."
            self.log_event(message, details=details)
    def resolve_attack(self, attacker, defender):
        att_str, def_str = attacker.zonal_strength[Position.FORWARD], defender.zonal_strength[Position.DEFENDER]
        prob = logistic_probability(att_str, def_str, ATTACK_SCALING)
        roll = random.random()
        if roll < prob:
            if self.logging_enabled:
                att_d = f"{attacker.base_zonal_strength[Position.FORWARD]:.1f} * {HOME_ADVANTAGE_BOOST} (H) -> {att_str:.1f}" if attacker.is_home else f"{att_str:.1f}"
                def_d = f"{defender.base_zonal_strength[Position.DEFENDER]:.1f} * {HOME_ADVANTAGE_BOOST} (H) -> {def_str:.1f}" if defender.is_home else f"{def_str:.1f}"
                details = (f"Attack: {attacker.team.name} vs {defender.team.name}\n- Att Fwd: {att_d}\n- Def Str: {def_d}\n- Prob to Create Chance: {prob:.1%}\n- Roll: {roll:.3f} -> Success")
                self.log_event(f"{attacker.team.name} creates a chance!", event_type='SHOT_OPPORTUNITY', details=details)
            self.resolve_shot(attacker, defender)
        else:
            self.possession = defender
            self.zone = 'M'
            if self.logging_enabled:
                att_d = f"{attacker.base_zonal_strength[Position.FORWARD]:.1f} * {HOME_ADVANTAGE_BOOST} (H) -> {att_str:.1f}" if attacker.is_home else f"{att_str:.1f}"
                def_d = f"{defender.base_zonal_strength[Position.DEFENDER]:.1f} * {HOME_ADVANTAGE_BOOST} (H) -> {def_str:.1f}" if defender.is_home else f"{def_str:.1f}"
                details = (f"Attack: {attacker.team.name} vs {defender.team.name}\n- Att Fwd: {att_d}\n- Def Str: {def_d}\n- Prob to Create Chance: {prob:.1%}\n- Roll: {roll:.3f} -> Fail")
                self.log_event(f"{defender.team.name}'s defense holds firm.", event_type='DEFENSIVE_STOP', details=details)
    def resolve_shot(self, attacker, defender):
        shooter = attacker.get_random_player([Position.FORWARD, Position.MIDFIELDER])
        goalkeeper = defender.get_goalkeeper()
        if not shooter or not goalkeeper:
            self.possession = defender
            self.zone = 'M'
            return
        prob = logistic_probability(shooter.effective_skill, goalkeeper.effective_skill, SHOT_SCALING) * GOAL_CONVERSION_FACTOR
        roll = random.random()
       
        if roll < prob:
            attacker.score += 1
            if self.logging_enabled:
                details = (f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n- Goal Prob: {prob:.1%}\n- Roll: {roll:.3f} -> GOAL")
                score_line = f"({self.team_a.score}-{self.team_b.score})"
                self.log_event(f"GOAL! {shooter.name} scores! {score_line}", importance='goal', event_type='GOAL', details=details)
        else:
            if self.logging_enabled:
                details = (f"Shot: {shooter.name} ({shooter.effective_skill:.1f}) vs {goalkeeper.name} ({goalkeeper.effective_skill:.1f})\n- Goal Prob: {prob:.1%}\n- Roll: {roll:.3f} -> NO GOAL")
                self.log_event(f"NO GOAL! Shot by {shooter.name}.", importance='miss', event_type='MISS', details=details)
       
        self.possession = defender
        self.zone = 'M'
   
    def get_results(self):
        return {'log': self.log, 'score_a': self.team_a.score, 'score_b': self.team_b.score, 'team_a_name': self.team_a.team.name, 'team_b_name': self.team_b.team.name}
def simulate_match(team_a_id, team_b_id):
    team_a, team_b = Team.query.get(team_a_id), Team.query.get(team_b_id)
    if not team_a or not team_b:
        return {'log': [{'message': 'Invalid Teams'}], 'score_a': 0, 'score_b': 0, 'team_a_name': '?', 'team_b_name': '?'}
    return MatchSimulator(team_a, team_b, logging_enabled=True).simulate()
def get_prematch_odds(user_team_id=None, enemy_team_id=None, simulations=100, user_team_model=None, enemy_team_model=None, fixed_user_lineup_ids=None):
    if not user_team_model:
        user_team_model = Team.query.get(user_team_id)
    if not enemy_team_model:
        enemy_team_model = Team.query.get(enemy_team_id)
    if not user_team_model or not enemy_team_model: return {'error': 'Invalid teams'}
    user_team_home = MatchTeam(user_team_model, is_home=True, fixed_lineup_ids=fixed_user_lineup_ids)
    user_team_away = MatchTeam(user_team_model, is_home=False, fixed_lineup_ids=fixed_user_lineup_ids)
    enemy_team_home = MatchTeam(enemy_team_model, is_home=True)
    enemy_team_away = MatchTeam(enemy_team_model, is_home=False)
    def _run_fixture_sims(home_team_model, away_team_model, fixed_home_ids=None, fixed_away_ids=None):
        wins, draws, losses, goals_for, goals_against = 0, 0, 0, 0, 0
        for _ in range(simulations):
            simulator = MatchSimulator(home_team_model, away_team_model, logging_enabled=False, fixed_a_ids=fixed_home_ids, fixed_b_ids=fixed_away_ids)
            result = simulator.simulate()
            goals_for += result['score_a']
            goals_against += result['score_b']
            if result['score_a'] > result['score_b']: wins += 1
            elif result['score_b'] > result['score_a']: losses += 1
            else: draws += 1
        return {'win_prob': (wins / simulations) * 100, 'draw_prob': (draws / simulations) * 100, 'loss_prob': (losses / simulations) * 100, 'avg_goals_for': goals_for / simulations, 'avg_goals_against': goals_against / simulations}
    home_fixture_probs = _run_fixture_sims(user_team_model, enemy_team_model, fixed_home_ids=fixed_user_lineup_ids, fixed_away_ids=None)
    away_fixture_probs = _run_fixture_sims(enemy_team_model, user_team_model, fixed_home_ids=None, fixed_away_ids=fixed_user_lineup_ids)
    return {
        'home_fixture': {'probs': home_fixture_probs, 'stats': {'user_team': user_team_home.get_stats_dict(), 'enemy_team': enemy_team_away.get_stats_dict()}},
        'away_fixture': {'probs': away_fixture_probs, 'stats': {'user_team': user_team_away.get_stats_dict(), 'enemy_team': enemy_team_home.get_stats_dict()}},
        'simulations_run': simulations
    }
