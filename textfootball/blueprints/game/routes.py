# textfootball/blueprints/game/routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from textfootball import db
from textfootball.models import User, Team, Player, Position, Message
import random
import statistics
from datetime import datetime
from textfootball.core.match_simulator import simulate_match, get_prematch_odds, MatchTeam

game_bp = Blueprint('game', __name__)

MAX_TEAMS = 3

FIRST_NAMES = ["Erik", "Lars", "Mikael", "Anders", "Johan", "Karl", "Fredrik"]
LAST_NAMES = ["Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson"]

def _generate_starter_squad(team):
    """
    Generates a starter squad for a new team, now including penalty-related skills.
    """
    positions = [Position.GOALKEEPER]*2 + [Position.DEFENDER]*6 + [Position.MIDFIELDER]*7 + [Position.FORWARD]*5
    random.shuffle(positions)
    available_numbers = list(range(1, 21))
    random.shuffle(available_numbers)
    for i in range(20):
        skill = random.randint(30, 70)
        current_pos = positions[i]

        # Free Kick ability: Correlated with skill but with high variance
        fk_ability = max(10, min(99, skill + random.randint(-15, 30)))
        
        # NEW: Penalty Taking: Similar correlation to FK ability, representing composure.
        pen_taking = max(10, min(99, skill + random.randint(-20, 20)))
        
        # NEW: Penalty Saving: Highly dependent on position. Goalkeepers are specialized.
        if current_pos == Position.GOALKEEPER:
            # Goalkeepers are naturally good at this
            pen_saving = max(40, min(90, skill + random.randint(5, 30)))
        else:
            # Outfield players are generally poor at saving penalties
            pen_saving = random.randint(5, 25)

        player = Player(
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            age=random.randint(18, 32),
            position=current_pos,
            skill=skill,
            free_kick_ability=fk_ability,
            penalty_taking=pen_taking,
            penalty_saving=pen_saving,
            potential=random.randint(60, 95),
            shape=random.randint(70, 100),
            shirt_number=available_numbers.pop(),
            team_id=team.id
        )
        db.session.add(player)

@game_bp.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('game.dashboard'))
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
    # Note: The user must update team_page.html to display the new penalty attributes.
    return render_template('team_page.html', team=team, players=sorted_players, is_owner=is_owner)

@game_bp.route('/delete-team/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    team = Team.query.get_or_404(team_id)
    user = User.query.filter_by(username=session['username']).first()
    if team.user_id != user.id:
        flash("You do not have permission to do that.", "danger")
        return redirect(url_for('game.dashboard'))
    db.session.delete(team)
    db.session.commit()
    flash(f"Team '{team.name}' has been deleted.", "success")
    if 'selected_team_id' in session and session['selected_team_id'] == team_id:
        session.pop('selected_team_id')
    return redirect(url_for('game.dashboard'))

@game_bp.route('/create-team', methods=['GET', 'POST'])
def create_team():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    user = User.query.filter_by(username=session['username']).first()
    if len(user.teams) >= MAX_TEAMS:
        flash(f"You have reached the maximum of {MAX_TEAMS} teams.", "warning")
        return redirect(url_for('game.dashboard'))
    if request.method == 'POST':
        team_name = request.form.get('name')
        country = request.form.get('country')
        existing_team = Team.query.filter_by(name=team_name).first()
        if existing_team:
            flash('That team name is already taken.', "danger")
            return redirect(url_for('game.create_team'))
        new_team = Team(name=team_name, country=country, user_id=user.id)
        db.session.add(new_team)
        db.session.commit()
        # This function now generates penalty skills
        _generate_starter_squad(new_team)
        db.session.commit()
        return redirect(url_for('game.dashboard'))
    return render_template('create_team.html')

@game_bp.route('/player/<int:player_id>')
def player_page(player_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    player = Player.query.get_or_404(player_id)
    user = User.query.filter_by(username=session['username']).first()
    is_owner = (player.team.user_id == user.id)
    # Note: The user must update player_page.html to display the new penalty attributes.
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
    """
    Handles challenges between teams. Now accepts a 'match_type' form parameter
    to determine if the match is a knockout game requiring a shootout on a draw.
    """
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    challenged_team = Team.query.get_or_404(team_id)
    user = User.query.filter_by(username=session['username']).first()

    if challenged_team.user_id == user.id:
        flash("You cannot challenge your own team.", "danger")
        return redirect(url_for('game.team_page', team_id=team_id))

    if 'selected_team_id' not in session:
        flash("Select one of your teams first to challenge with.", "warning")
        return redirect(url_for('game.dashboard'))

    challenger_team = Team.query.get(session['selected_team_id'])

    if challenger_team is None or challenger_team.user_id != user.id:
        flash("Invalid selected team.", "danger")
        return redirect(url_for('game.team_page', team_id=team_id))

    num_sims = int(request.form.get('num_sims', 1))
    num_sims = max(1, min(num_sims, 10))
    
    # NEW: Check if the match is a 'knockout' type from the form.
    # The 'why': This allows the user to trigger matches that require a winner,
    # enabling cup competitions or high-stakes single matches.
    is_knockout = request.form.get('match_type') == 'knockout'

    results = []
    for _ in range(num_sims):
        # NEW: The is_knockout flag is passed to the simulation engine.
        sim_result = simulate_match(challenger_team.id, challenged_team.id, is_knockout=is_knockout)
        results.append(sim_result)
        
    # The user must update match_result.html to display shootout scores if they exist.
    # Passing is_knockout to the template can help with conditional rendering.
    return render_template('match_result.html', results=results, is_knockout=is_knockout)

@game_bp.route('/mailbox')
def mailbox():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    user = User.query.filter_by(username=session['username']).first()
    received = Message.query.filter_by(recipient_id=user.id).order_by(Message.timestamp.desc()).all()
    sent = Message.query.filter_by(sender_id=user.id).order_by(Message.timestamp.desc()).all()
    return render_template('mailbox.html', received=received, sent=sent)

@game_bp.route('/compose', methods=['GET', 'POST'])
def compose():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    if request.method == 'POST':
        recipient_username = request.form.get('recipient')
        subject = request.form.get('subject')
        body = request.form.get('body')
        sender = User.query.filter_by(username=session['username']).first()
        recipient = User.query.filter_by(username=recipient_username).first()
        if not recipient:
            flash(f"User '{recipient_username}' not found.", 'danger')
            return render_template('compose.html', subject=subject, body=body, recipient=recipient_username)
        if recipient.id == sender.id:
            flash("You cannot send a message to yourself.", 'warning')
            return render_template('compose.html', subject=subject, body=body, recipient=recipient_username)
        message = Message(sender_id=sender.id, recipient_id=recipient.id, subject=subject, body=body)
        db.session.add(message)
        db.session.commit()
        flash('Your message has been sent.', 'success')
        return redirect(url_for('game.mailbox'))
    recipient = request.args.get('recipient', '')
    return render_template('compose.html', recipient=recipient)

@game_bp.route('/mail/<int:message_id>')
def view_mail(message_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    message = Message.query.get_or_404(message_id)
    user = User.query.filter_by(username=session['username']).first()
    if message.recipient_id != user.id and message.sender_id != user.id:
        flash("You do not have permission to view this message.", "danger")
        return redirect(url_for('game.mailbox'))
    if message.recipient_id == user.id and not message.is_read:
        message.is_read = True
        db.session.commit()
    return render_template('view_mail.html', message=message)

@game_bp.route('/delete_mail/<int:message_id>', methods=['POST'])
def delete_mail(message_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    user = User.query.filter_by(username=session['username']).first()
    message = Message.query.get_or_404(message_id)
    if message.sender_id != user.id and message.recipient_id != user.id:
        flash("You do not have permission to delete this message.", "danger")
        return redirect(url_for('game.mailbox'))
    db.session.delete(message)
    db.session.commit()
    flash("Message deleted successfully.", "success")
    return redirect(url_for('game.mailbox'))

@game_bp.route('/accept_challenge/<int:message_id>', methods=['POST'])
def accept_challenge(message_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    message = Message.query.get_or_404(message_id)
    user = User.query.filter_by(username=session['username']).first()
    if message.recipient_id != user.id or not message.is_challenge:
        flash("Invalid challenge.", "danger")
        return redirect(url_for('game.mailbox'))
    if message.is_accepted:
        flash("Challenge already accepted.", "info")
        return redirect(url_for('game.view_mail', message_id=message_id))
    message.is_accepted = True
    response = Message(sender_id=user.id, recipient_id=message.sender_id, subject=f"Re: {message.subject}", body=f"{user.username} has accepted your challenge.")
    db.session.add(response)
    db.session.commit()
    # Assuming challenges are friendly (not knockout) unless specified otherwise.
    # For a more advanced system, the match type could be stored in the message.
    results = [simulate_match(message.challenger_team_id, message.challenged_team_id, is_knockout=False)]
    return render_template('match_result.html', results=results, is_knockout=False)

@game_bp.route('/simulate')
def simulate():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    user = User.query.filter_by(username=session['username']).first()
    all_teams = Team.query.filter(Team.user_id != user.id).all()
    user_team_id = session.get('selected_team_id')
    enemies = []
    for team in all_teams:
        odds = None
        if user_team_id:
            odds = get_prematch_odds(user_team_id=user_team_id, enemy_team_id=team.id)
        enemies.append({'team': team, 'odds': odds})
    return render_template('simulate.html', enemies=enemies, has_selected_team=(user_team_id is not None))

@game_bp.route('/workbench')
def workbench():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    user_team_id = session.get('selected_team_id')
    if not user_team_id:
        flash("Please select a team from the dashboard to use the Balancing Workbench.", "warning")
        return redirect(url_for('game.dashboard'))

    user = User.query.filter_by(username=session['username']).first()
    user_team = Team.query.get(user_team_id)

    # FIX: Add a check to ensure the team was actually found in the database.
    # The 'why': The session could contain an ID for a team that has since been deleted.
    # This check prevents an AttributeError if Team.query.get() returns None.
    if not user_team:
        flash("The selected team could not be found. It may have been deleted. Please select another team.", "warning")
        # Clean up the bad ID from the session
        session.pop('selected_team_id', None)
        return redirect(url_for('game.dashboard'))

    # This check is now safe because we know user_team is not None.
    if user_team.user_id != user.id:
        flash("You do not own this team. Please select one of your teams.", "danger")
        session.pop('selected_team_id', None)
        return redirect(url_for('game.dashboard'))

    match_team_instance = MatchTeam(user_team)
    starting_11 = match_team_instance.get_starting_11()
    session['workbench_fixed_lineup_ids'] = [p.id for p in starting_11]

    position_order = {Position.GOALKEEPER: 0, Position.DEFENDER: 1, Position.MIDFIELDER: 2, Position.FORWARD: 3}
    all_players = sorted(user_team.players, key=lambda p: (position_order[p.position], -p.effective_skill))

    starting_11_ids = set(session['workbench_fixed_lineup_ids'])
    all_other_teams = Team.query.filter(Team.id != user_team_id).order_by(Team.name).all()

    # Note: The user must update balancing_workbench.html to allow editing the new penalty attributes.
    return render_template('balancing_workbench.html',
                           user_team=user_team,
                           all_players=all_players,
                           starting_11_ids=starting_11_ids,
                           all_other_teams=all_other_teams)

@game_bp.route('/recalculate_odds', methods=['POST'])
def recalculate_odds():
    if 'username' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json()
    if not data or 'enemy_team_id' not in data or 'user_team_players' not in data:
        return jsonify({'error': 'Invalid request data'}), 400

    user_team_id = session.get('selected_team_id')
    if not user_team_id:
        return jsonify({'error': 'No team selected'}), 400

    user_team_model = Team.query.get(user_team_id)
    enemy_team_model = Team.query.get(data.get('enemy_team_id'))
    if not user_team_model or not enemy_team_model:
        return jsonify({'error': 'Invalid team ID provided'}), 404

    # Update modified_stats to include the new attributes
    modified_stats = {
        int(p['id']): {
            'skill': int(p['skill']),
            'shape': int(p['shape']),
            'free_kick_ability': int(p.get('free_kick_ability', 50)),
            'penalty_taking': int(p.get('penalty_taking', 50)) # Handle penalty taking
        } for p in data['user_team_players']
    }

    for player in user_team_model.players:
        if player.id in modified_stats:
            player.skill = modified_stats[player.id]['skill']
            player.shape = modified_stats[player.id]['shape']
            player.free_kick_ability = modified_stats[player.id]['free_kick_ability']
            player.penalty_taking = modified_stats[player.id]['penalty_taking']

    fixed_lineup_ids = session.get('workbench_fixed_lineup_ids')
    odds = get_prematch_odds(user_team_model=user_team_model, enemy_team_model=enemy_team_model, fixed_user_lineup_ids=fixed_lineup_ids)

    db.session.expunge_all() # Expunge all to avoid keeping temporary changes
    return jsonify(odds)

@game_bp.route('/batch_odds', methods=['POST'])
def batch_odds():
    """
    Runs the analytical simulator X times and returns aggregate statistics.
    """
    if 'username' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json()
    if not data or 'enemy_team_id' not in data or 'user_team_players' not in data or 'runs' not in data:
        return jsonify({'error': 'Invalid request data'}), 400

    user_team_id = session.get('selected_team_id')
    if not user_team_id:
        return jsonify({'error': 'No team selected'}), 400

    runs = int(data.get('runs', 10))
    runs = max(1, min(runs, 100))

    user_team_model = Team.query.get(user_team_id)
    enemy_team_model = Team.query.get(data.get('enemy_team_id'))
    if not user_team_model or not enemy_team_model:
        return jsonify({'error': 'Invalid team ID provided'}), 404

    # Apply temporary edits (in-memory only) - Updated for new attributes
    modified_stats = {
        int(p['id']): {
            'skill': int(p['skill']),
            'shape': int(p['shape']),
            'free_kick_ability': int(p.get('free_kick_ability', 50)),
            'penalty_taking': int(p.get('penalty_taking', 50))
        } for p in data['user_team_players']
    }
    for player in user_team_model.players:
        if player.id in modified_stats:
            player.skill = modified_stats[player.id]['skill']
            player.shape = modified_stats[player.id]['shape']
            player.free_kick_ability = modified_stats[player.id]['free_kick_ability']
            player.penalty_taking = modified_stats[player.id]['penalty_taking']

    fixed_lineup_ids = session.get('workbench_fixed_lineup_ids')

    # Accumulators
    user_home_acc = {'win_prob': [], 'draw_prob': [], 'loss_prob': [], 'avg_goals_for': [], 'avg_goals_against': []}
    user_away_acc = {'win_prob': [], 'draw_prob': [], 'loss_prob': [], 'avg_goals_for': [], 'avg_goals_against': []}
    enemy_home_acc = {'win_prob': [], 'draw_prob': [], 'loss_prob': [], 'avg_goals_for': [], 'avg_goals_against': []}
    enemy_away_acc = {'win_prob': [], 'draw_prob': [], 'loss_prob': [], 'avg_goals_for': [], 'avg_goals_against': []}

    sims_per_run = None

    for _ in range(runs):
        res = get_prematch_odds(
            user_team_model=user_team_model,
            enemy_team_model=enemy_team_model,
            fixed_user_lineup_ids=fixed_lineup_ids
        )
        sims_per_run = res.get('simulations_run', sims_per_run)

        hf = res['home_fixture']['probs']  # user at home
        af = res['away_fixture']['probs']  # enemy at home

        # User perspective (home)
        user_home_acc['win_prob'].append(float(hf['win_prob']))
        user_home_acc['draw_prob'].append(float(hf['draw_prob']))
        user_home_acc['loss_prob'].append(float(hf['loss_prob']))
        user_home_acc['avg_goals_for'].append(float(hf['avg_goals_for']))
        user_home_acc['avg_goals_against'].append(float(hf['avg_goals_against']))

        # User perspective (away) — flip away fixture
        user_away_acc['win_prob'].append(float(af['loss_prob']))
        user_away_acc['draw_prob'].append(float(af['draw_prob']))
        user_away_acc['loss_prob'].append(float(af['win_prob']))
        user_away_acc['avg_goals_for'].append(float(af['avg_goals_against']))
        user_away_acc['avg_goals_against'].append(float(af['avg_goals_for']))

        # Enemy perspective (home) — away fixture as-is
        enemy_home_acc['win_prob'].append(float(af['win_prob']))
        enemy_home_acc['draw_prob'].append(float(af['draw_prob']))
        enemy_home_acc['loss_prob'].append(float(af['loss_prob']))
        enemy_home_acc['avg_goals_for'].append(float(af['avg_goals_for']))
        enemy_home_acc['avg_goals_against'].append(float(af['avg_goals_against']))

        # Enemy perspective (away) — flip user home fixture
        enemy_away_acc['win_prob'].append(float(hf['loss_prob']))
        enemy_away_acc['draw_prob'].append(float(hf['draw_prob']))
        enemy_away_acc['loss_prob'].append(float(hf['win_prob']))
        enemy_away_acc['avg_goals_for'].append(float(hf['avg_goals_against']))
        enemy_away_acc['avg_goals_against'].append(float(hf['avg_goals_for']))

    def summarize(acc):
        means = {k: (statistics.fmean(v) if v else 0.0) for k, v in acc.items()}
        stddevs = {k: (statistics.pstdev(v) if len(v) > 1 else 0.0) for k, v in acc.items()}
        return {'means': means, 'stddevs': stddevs}

    db.session.expunge_all() # Expunge all to avoid keeping temporary changes

    return jsonify({
        'runs': runs,
        'simulations_per_run': sims_per_run,
        'user_team_name': user_team_model.name,
        'enemy_team_name': enemy_team_model.name,
        'user': {
            'home': summarize(user_home_acc),
            'away': summarize(user_away_acc)
        },
        'enemy': {
            'home': summarize(enemy_home_acc),
            'away': summarize(enemy_away_acc)
        }
    })
