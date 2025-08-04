from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from app import db
from .models import User, Team, Player, Position
import random

game_bp = Blueprint('game_bp', __name__)

# Mock data for player generation (can be moved later)
FIRST_NAMES = ["Erik", "Lars", "Mikael", "Anders", "Johan", "Karl", "Fredrik"]
LAST_NAMES = ["Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson"]

def _generate_starter_squad(team):
    """Creates 20 players and adds them to the database for the given team."""
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
            potential=random.randint(60, 95), # UV
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
    return render_template('dashboard.html', user=user)

@game_bp.route('/team/<int:team_id>')
def team_page(team_id):
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    team = Team.query.get_or_404(team_id)
    user = User.query.filter_by(username=session['username']).first()

    # Security Check: Make sure the logged-in user owns this team
    if team.user_id != user.id:
        flash("You do not have permission to view this page.")
        return redirect(url_for('game_bp.dashboard'))

    return render_template('team_page.html', team=team)

@game_bp.route('/create-team', methods=['GET', 'POST'])
def create_team():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    user = User.query.filter_by(username=session['username']).first()
    if user.team:
        return redirect(url_for('game_bp.dashboard'))

    if request.method == 'POST':
        team_name = request.form.get('name')
        country = request.form.get('country')
        
        existing_team = Team.query.filter_by(name=team_name).first()
        if existing_team:
            flash('That team name is already taken.')
            return redirect(url_for('game_bp.create_team'))
        
        new_team = Team(name=team_name, country=country, user_id=user.id)
        db.session.add(new_team)
        db.session.commit()
        
        _generate_starter_squad(new_team)
        db.session.commit()
        
        return redirect(url_for('game_bp.dashboard'))

    return render_template('create_team.html')
