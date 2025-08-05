from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from app import db
from .models import User, Team, Player, Position, Message
import random
from datetime import datetime
from .match_sim import simulate_match

game_bp = Blueprint('game_bp', __name__)

MAX_TEAMS = 3

FIRST_NAMES = ["Erik", "Lars", "Mikael", "Anders", "Johan", "Karl", "Fredrik"]
LAST_NAMES = ["Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson"]

def _generate_starter_squad(team):
    # Adjusted distribution to ensure enough players for a 4-4-2 lineup.
    # 2 GK, 6 DEF, 7 MID, 5 FWD = 20 Players
    positions = [Position.GOALKEEPER]*2 + [Position.DEFENDER]*6 + [Position.MIDFIELDER]*7 + [Position.FORWARD]*5
    random.shuffle(positions)

    available_numbers = list(range(1, 21))
    random.shuffle(available_numbers)
    for i in range(20):
        player = Player(
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            age=random.randint(18, 32),
            position=positions[i],
            # Increased skill range (was 20-50) for better differentiation in the new engine
            skill=random.randint(30, 70),
            potential=random.randint(60, 95),
            shape=random.randint(70, 100),
            shirt_number=available_numbers.pop(),
            team_id=team.id
        )
        db.session.add(player)

# ... (The rest of the routes remain identical to the provided input, but are included below for completeness) ...

@game_bp.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('game_bp.dashboard'))
    return render_template('index.html')

@game_bp.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    user = User.query.filter_by(username=session['username']).first()
    return render_template('dashboard.html', user=user, max_teams=MAX_TEAMS)

@game_bp.route('/team/<int:team_id>')
def team_page(team_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    team = Team.query.get_or_404(team_id)
    user = User.query.filter_by(username=session['username']).first()
    is_owner = (team.user_id == user.id)
    if is_owner:
        session['selected_team_id'] = team.id

    position_order = {Position.GOALKEEPER: 0, Position.DEFENDER: 1, Position.MIDFIELDER: 2, Position.FORWARD: 3}
    sorted_players = sorted(team.players, key=lambda p: (position_order[p.position], p.shirt_number))
    return render_template('team_page.html', team=team, players=sorted_players, is_owner=is_owner)

@game_bp.route('/delete-team/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    team = Team.query.get_or_404(team_id)
    user = User.query.filter_by(username=session['username']).first()
    if team.user_id != user.id:
        flash("You do not have permission to do that.", "danger")
        return redirect(url_for('game_bp.dashboard'))

    db.session.delete(team)
    db.session.commit()
    flash(f"Team '{team.name}' has been deleted.", "success")
    if 'selected_team_id' in session and session['selected_team_id'] == team_id:
        session.pop('selected_team_id')
    return redirect(url_for('game_bp.dashboard'))

@game_bp.route('/create-team', methods=['GET', 'POST'])
def create_team():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    user = User.query.filter_by(username=session['username']).first()

    if len(user.teams) >= MAX_TEAMS:
        flash(f"You have reached the maximum of {MAX_TEAMS} teams.", "warning")
        return redirect(url_for('game_bp.dashboard'))
    if request.method == 'POST':
        team_name = request.form.get('name')
        country = request.form.get('country')

        existing_team = Team.query.filter_by(name=team_name).first()
        if existing_team:
            flash('That team name is already taken.', "danger")
            return redirect(url_for('game_bp.create_team'))

        new_team = Team(name=team_name, country=country, user_id=user.id)
        db.session.add(new_team)
        db.session.commit()

        _generate_starter_squad(new_team)
        db.session.commit()

        return redirect(url_for('game_bp.dashboard'))
    return render_template('create_team.html')

@game_bp.route('/player/<int:player_id>')
def player_page(player_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))


    player = Player.query.get_or_404(player_id)
    user = User.query.filter_by(username=session['username']).first()
    is_owner = (player.team.user_id == user.id)
    return render_template('player_page.html', player=player, is_owner=is_owner)

@game_bp.route('/coming-soon')
def coming_soon():
    return render_template('coming_soon.html')

@game_bp.route('/search', methods=['GET', 'POST'])
def search():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    query = ''
    users = []
    teams = []
    if request.method == 'POST':
        query = request.form.get('query', '')
        if query:
            users = User.query.filter(User.username.ilike(f'%{query}%')).all()
            teams = Team.query.filter(Team.name.ilike(f'%{query}%')).all()

    return render_template('search.html', query=query, users=users, teams=teams)

@game_bp.route('/user/<username>')
def user_profile(username):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    profile_user = User.query.filter_by(username=username).first_or_404()
    return render_template('user_profile.html', profile_user=profile_user)

@game_bp.route('/challenge/<int:team_id>', methods=['POST'])
def challenge_team(team_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    challenged_team = Team.query.get_or_404(team_id)
    user = User.query.filter_by(username=session['username']).first()

    if challenged_team.user_id == user.id:
        flash("You cannot challenge your own team.", "danger")
        return redirect(url_for('game_bp.team_page', team_id=team_id))

    if 'selected_team_id' not in session:
        flash("Select one of your teams first to challenge with.", "warning")
        return redirect(url_for('game_bp.dashboard'))

    challenger_team = Team.query.get(session['selected_team_id'])
    if challenger_team is None or challenger_team.user_id != user.id:
        flash("Invalid selected team.", "danger")
        return redirect(url_for('game_bp.team_page', team_id=team_id))

    num_sims = int(request.form.get('num_sims', 1))
    num_sims = max(1, min(num_sims, 10))

    results = []
    for _ in range(num_sims):
        # Challenger is Team A (Home) vs Challenged is Team B (Away)
        sim_result = simulate_match(challenger_team.id, challenged_team.id)
        results.append(sim_result)

    return render_template('match_result.html', results=results)

@game_bp.route('/mailbox')
def mailbox():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    user = User.query.filter_by(username=session['username']).first()
    received = Message.query.filter_by(recipient_id=user.id).order_by(Message.timestamp.desc()).all()
    sent = Message.query.filter_by(sender_id=user.id).order_by(Message.timestamp.desc()).all()

    return render_template('mailbox.html', received=received, sent=sent)

@game_bp.route('/mail/<int:message_id>')
def view_mail(message_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    message = Message.query.get_or_404(message_id)
    user = User.query.filter_by(username=session['username']).first()

    if message.recipient_id != user.id and message.sender_id != user.id:
        flash("You do not have permission to view this message.", "danger")
        return redirect(url_for('game_bp.mailbox'))

    if message.recipient_id == user.id and not message.is_read:
        message.is_read = True
        db.session.commit()

    return render_template('view_mail.html', message=message)

@game_bp.route('/accept_challenge/<int:message_id>', methods=['POST'])
def accept_challenge(message_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    message = Message.query.get_or_404(message_id)
    user = User.query.filter_by(username=session['username']).first()

    if message.recipient_id != user.id or not message.is_challenge:
        flash("Invalid challenge.", "danger")
        return redirect(url_for('game_bp.mailbox'))

    if message.is_accepted:
        flash("Challenge already accepted.", "info")
        return redirect(url_for('game_bp.view_mail', message_id=message_id))

    message.is_accepted = True
    db.session.commit()

    challenged_team = Team.query.get(message.challenged_team_id)
    challenger_team = Team.query.get(message.challenger_team_id)

    response = Message(
        sender_id=user.id,
        recipient_id=message.sender_id,
        subject=f"Challenge Accepted: {challenged_team.name} vs {challenger_team.name}",
        body=f"{user.username} has accepted your challenge. The friendly match between {challenged_team.name} and {challenger_team.name} is accepted."
    )
    db.session.add(response)
    db.session.commit()

    # In a formal challenge acceptance, the challenged team (A) might host the challenger (B), or vice-versa.
    # We'll stick to Challenger (A) vs Challenged (B) for consistency here.
    results = [simulate_match(challenger_team.id, challenged_team.id)]
    return render_template('match_result.html', results=results)

# ... (send_message, compose, delete_mail routes are unchanged)

@game_bp.route('/simulate')
def simulate():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    user = User.query.filter_by(username=session['username']).first()
    all_teams = Team.query.filter(Team.user_id != user.id).all() # All other teams as "enemies"

    enemies = []
    for team in all_teams:
        players = team.players
        # Provide a simple overview using the new effective skill calculation
        avg_skill = sum(p.skill for p in players) / len(players) if players else 0
        avg_effective_skill = sum(p.effective_skill for p in players) / len(players) if players else 0
        
        # Updated info text to reflect the new engine's metrics
        info = f"Avg Base Skill: {avg_skill:.1f}. Avg Effective Skill (with Shape): {avg_effective_skill:.1f}."
        enemies.append({'team': team, 'info': info})

    return render_template('simulate.html', enemies=enemies)
