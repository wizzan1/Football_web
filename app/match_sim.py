from app import db
from .models import Team, Player
import random

def simulate_match(team_a_id, team_b_id):
    team_a = Team.query.get(team_a_id)
    team_b = Team.query.get(team_b_id)
    
    if not team_a or not team_b:
        return {'error': 'Invalid teams'}
    
    # Random select 11 players (or all if less)
    players_a = random.sample(team_a.players, min(11, len(team_a.players)))
    players_b = random.sample(team_b.players, min(11, len(team_b.players)))
    
    avg_skill_a = sum(p.skill for p in players_a) / len(players_a) if players_a else 0
    avg_skill_b = sum(p.skill for p in players_b) / len(players_b) if players_b else 0
    
    # Prematch summary
    prematch = f"Team A ({team_a.name}) Avg Skill: {avg_skill_a:.1f} - Stronger attacks expected if > enemy.\n"
    prematch += f"Team B ({team_b.name}) Avg Skill: {avg_skill_b:.1f} - Defense holds if close; randomness adds 2-5% variance per shot.\n"
    prematch += "Match: 90 mins, ~8-12 events; goals on skill-weighted probs + random, tuned for ~2-3 total goals."
    
    # Sim vars
    score_a = 0
    score_b = 0
    log = [prematch]
    
    for minute in range(1, 91, 10):  # Chunks
        possession_a = avg_skill_a / (avg_skill_a + avg_skill_b) if (avg_skill_a + avg_skill_b) > 0 else 0.5
        possession_a += random.uniform(-0.05, 0.05)
        possession_a = max(0.4, min(0.6, possession_a))  # Tighter cap for less swing
        
        shots_a = int(possession_a * 1.2 + random.uniform(0, 0.8))  # Slightly higher shots for more action
        shots_b = int((1 - possession_a) * 1.2 + random.uniform(0, 0.8))
        
        for _ in range(shots_a):
            prob = 0.15 + (avg_skill_a - avg_skill_b) / 100 + random.uniform(0.03, 0.07)  # Raised base for goals
            if prob > 0.20:  # Lower threshold
                score_a += 1
                log.append(f"Min {minute}-{minute+9}: Team A GOAL! (prob {prob:.2f})")
            else:
                log.append(f"Min {minute}-{minute+9}: Team A shot - missed (prob {prob:.2f})")
        
        for _ in range(shots_b):
            prob = 0.15 + (avg_skill_b - avg_skill_a) / 100 + random.uniform(0.03, 0.07)
            if prob > 0.20:
                score_b += 1
                log.append(f"Min {minute}-{minute+9}: Team B GOAL! (prob {prob:.2f})")
            else:
                log.append(f"Min {minute}-{minute+9}: Team B shot - missed (prob {prob:.2f})")
    
    result = f"Final: {team_a.name} {score_a} - {score_b} {team_b.name}"
    log.append(result)
    
    return {'log': log, 'score_a': score_a, 'score_b': score_b, 'team_a_name': team_a.name, 'team_b_name': team_b.name}
