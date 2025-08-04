# app/routes_game.py (updated with search and user_profile routes, removed ownership checks for viewing)
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from app import db
from .models import User, Team, Player, Position
import random

game_bp = Blueprint('game_bp', __name__)

MAX_TEAMS = 3

FIRST_NAMES = ["Erik", "Lars", "Mikael", "Anders", "Johan", "Karl", "Fredrik"]
LAST_NAMES = ["Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson"]

def _generate_starter_squad(team):
    positions = [Position.GOALKEEPER]*2 + [Position.DEFENDER]*7 + [Position.MIDFIELDER]*7 + [Position.FORWARD]*4
    random.shuffle(positions)
   
    available_numbers = list(range(1, 21))
    random.shuffle(available_numbers)
    for i in range(20):
        player = Player(
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            age=random.randint(18, 32),
            position=positions[i],
            skill=random.randint(20, 50),
            potential=random.randint(60, 95),
            shape=random.randint(70, 100),
            shirt_number=available_numbers.pop(),
            team_id=team.id
        )
        db.session.add(player)

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
    # Removed ownership check to allow public viewing
   
    # NEW: Set the selected team in session only if owned by the user
    user = User.query.filter_by(username=session['username']).first()
    if team.user_id == user.id:
        session['selected_team_id'] = team.id
   
    # Custom sorting logic
    position_order = {Position.GOALKEEPER: 0, Position.DEFENDER: 1, Position.MIDFIELDER: 2, Position.FORWARD: 3}
   
    sorted_players = sorted(team.players, key=lambda p: (position_order[p.position], p.shirt_number))
    return render_template('team_page.html', team=team, players=sorted_players, is_owner=(team.user_id == user.id))

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
    # Clear selected team if it was the deleted one
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

# Route to view individual player details
@game_bp.route('/player/<int:player_id>')
def player_page(player_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))

    player = Player.query.get_or_404(player_id)
    # Removed ownership check to allow public viewing
    user = User.query.filter_by(username=session['username']).first()
    is_owner = (player.team.user_id == user.id)
    return render_template('player_page.html', player=player, is_owner=is_owner)

# Stub route for coming soon features
@game_bp.route('/coming-soon')
def coming_soon():
    return render_template('coming_soon.html')

# NEW: Route for searching users and teams
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

# NEW: Route for viewing user profile
@game_bp.route('/user/<username>')
def user_profile(username):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    profile_user = User.query.filter_by(username=username).first_or_404()
    return render_template('user_profile.html', profile_user=profile_user)
