from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from app import db
from .models import User, Team

game_bp = Blueprint('game_bp', __name__)

@game_bp.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('game_bp.dashboard'))
    return render_template('index.html')

@game_bp.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    # Get the user object from the database
    user = User.query.filter_by(username=session['username']).first()
    # The user's team is now accessible via user.team
    return render_template('dashboard.html', user=user)

@game_bp.route('/create-team', methods=['GET', 'POST'])
def create_team():
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    user = User.query.filter_by(username=session['username']).first()
    if user.team:
        # If user already has a team, redirect them to the dashboard
        return redirect(url_for('game_bp.dashboard'))

    if request.method == 'POST':
        team_name = request.form.get('name')
        country = request.form.get('country')
        
        # Check if team name is already taken
        existing_team = Team.query.filter_by(name=team_name).first()
        if existing_team:
            flash('That team name is already taken.')
            return redirect(url_for('game_bp.create_team'))
        
        # Create new team and link it to the current user
        new_team = Team(name=team_name, country=country, user_id=user.id)
        db.session.add(new_team)
        db.session.commit()
        
        return redirect(url_for('game_bp.dashboard'))

    return render_template('create_team.html')
