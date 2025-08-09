# textfootball/blueprints/league/routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from textfootball import db
from textfootball.models.user import User
from textfootball.models.team import Team
from textfootball.models.league import League, LeagueTeam, Fixture, LeagueStatus
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random

league_bp = Blueprint('league', __name__, url_prefix='/league')

@league_bp.route('/')
def index():
    """Main league hub - shows user's leagues and options"""
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        flash('User not found. Please login again.', 'danger')
        return redirect(url_for('auth_bp.login'))
    
    # Get user's teams that are in leagues
    my_leagues = []
    for team in user.teams:
        for participation in team.league_participations:
            my_leagues.append({
                'league': participation.league,
                'team': team,
                'participation': participation
            })
    
    return render_template('league/index.html', my_leagues=my_leagues)

@league_bp.route('/browse')
def browse():
    """Browse available leagues to join"""
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    # Get all recruiting leagues
    public_leagues = League.query.filter_by(
        is_public=True, 
        status=LeagueStatus.RECRUITING
    ).all()
    
    # Filter to show only leagues with space
    available_leagues = [l for l in public_leagues if not l.is_full]
    
    return render_template('league/browse.html', leagues=available_leagues)

@league_bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create a new league"""
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    if request.method == 'POST':
        user = User.query.filter_by(username=session['username']).first()
        
        # Get form data
        name = request.form.get('name')
        description = request.form.get('description', '')
        is_public = request.form.get('is_public') == 'true'
        password = request.form.get('password', '')
        max_teams = int(request.form.get('max_teams', 10))
        
        # Validate
        if not name:
            flash('League name is required', 'danger')
            return redirect(url_for('league.create'))
        
        if League.query.filter_by(name=name).first():
            flash('A league with that name already exists', 'danger')
            return redirect(url_for('league.create'))
        
        # Create the league
        new_league = League(
            name=name,
            description=description,
            creator_id=user.id,
            is_public=is_public,
            password=generate_password_hash(password) if password else None,
            max_teams=max_teams,
            min_teams=min(4, max_teams)  # Minimum 4 or max, whichever is smaller
        )
        
        db.session.add(new_league)
        db.session.commit()
        
        flash(f'League "{name}" created successfully!', 'success')
        return redirect(url_for('league.view', league_id=new_league.id))
    
    return render_template('league/create.html')

@league_bp.route('/<int:league_id>')
def view(league_id):
    """View a specific league"""
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    league = League.query.get_or_404(league_id)
    user = User.query.filter_by(username=session['username']).first()
    
    # Check if user has a team in this league
    user_participation = None
    user_team = None
    for team in user.teams:
        for participation in team.league_participations:
            if participation.league_id == league_id:
                user_participation = participation
                user_team = team
                break
    
    # Get league standings
    standings = sorted(
        league.league_teams,
        key=lambda x: (-x.points, -x.goal_difference, -x.goals_for)
    )
    
    # Update positions
    for i, team_entry in enumerate(standings, 1):
        team_entry.position = i
    
    # Get upcoming fixtures
    upcoming_fixtures = Fixture.query.filter_by(
        league_id=league_id,
        is_played=False
    ).order_by(Fixture.round, Fixture.id).limit(5).all()
    
    # Get recent results
    recent_results = Fixture.query.filter_by(
        league_id=league_id,
        is_played=True
    ).order_by(Fixture.round.desc(), Fixture.id.desc()).limit(5).all()
    
    return render_template('league/view.html',
                         league=league,
                         standings=standings,
                         user_participation=user_participation,
                         user_team=user_team,
                         upcoming_fixtures=upcoming_fixtures,
                         recent_results=recent_results,
                         is_creator=(user.id == league.creator_id))

@league_bp.route('/<int:league_id>/join', methods=['POST'])
def join(league_id):
    """Join a league with selected team"""
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    league = League.query.get_or_404(league_id)
    user = User.query.filter_by(username=session['username']).first()
    
    # Check if league is full
    if league.is_full:
        flash('This league is full', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Check if league is still recruiting
    if league.status != LeagueStatus.RECRUITING:
        flash('This league is no longer accepting new teams', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Get selected team
    team_id = request.form.get('team_id')
    if not team_id:
        flash('Please select a team to join with', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    team = Team.query.get_or_404(team_id)
    
    # Verify team ownership
    if team.user_id != user.id:
        flash('You can only join with your own teams', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Check if team is already in a league
    if team.league_participations:
        flash('This team is already in a league', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Check password if private
    if not league.is_public and league.password:
        password = request.form.get('password', '')
        if not check_password_hash(league.password, password):
            flash('Incorrect password', 'danger')
            return redirect(url_for('league.view', league_id=league_id))
    
    # Join the league
    league_team = LeagueTeam(
        league_id=league_id,
        team_id=team.id
    )
    db.session.add(league_team)
    
    # Check if league is now full and should auto-start
    if league.is_full and league.status == LeagueStatus.RECRUITING:
        league.status = LeagueStatus.READY
        flash(f'League is now full! Season will begin soon.', 'info')
    
    db.session.commit()
    
    flash(f'{team.name} has joined {league.name}!', 'success')
    return redirect(url_for('league.view', league_id=league_id))

@league_bp.route('/<int:league_id>/leave', methods=['POST'])
def leave(league_id):
    """Leave a league"""
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    league = League.query.get_or_404(league_id)
    user = User.query.filter_by(username=session['username']).first()
    
    # Can only leave during recruiting phase
    if league.status != LeagueStatus.RECRUITING:
        flash('Cannot leave a league once the season has started', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    team_id = request.form.get('team_id')
    team = Team.query.get_or_404(team_id)
    
    # Verify ownership
    if team.user_id != user.id:
        flash('Invalid team', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Find and remove participation
    participation = LeagueTeam.query.filter_by(
        league_id=league_id,
        team_id=team_id
    ).first()
    
    if participation:
        db.session.delete(participation)
        db.session.commit()
        flash(f'{team.name} has left the league', 'success')
    
    return redirect(url_for('league.index'))

@league_bp.route('/<int:league_id>/start', methods=['POST'])
def start(league_id):
    """Start a league (creator only)"""
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    league = League.query.get_or_404(league_id)
    user = User.query.filter_by(username=session['username']).first()
    
    # Check if user is creator
    if league.creator_id != user.id:
        flash('Only the league creator can start the season', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Check if enough teams
    if not league.can_start:
        flash(f'Need at least {league.min_teams} teams to start', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Check status
    if league.status != LeagueStatus.RECRUITING:
        flash('League has already started', 'danger')
        return redirect(url_for('league.view', league_id=league_id))
    
    # Generate fixtures
    generate_fixtures(league)
    
    # Update league status
    league.status = LeagueStatus.ACTIVE
    league.start_date = datetime.utcnow()
    league.current_round = 1
    
    db.session.commit()
    
    flash('League season has started! Fixtures have been generated.', 'success')
    return redirect(url_for('league.view', league_id=league_id))

def generate_fixtures(league):
    """Generate round-robin fixtures for a league"""
    teams = [lt.team_id for lt in league.league_teams]
    
    if len(teams) % 2 == 1:
        teams.append(None)  # Bye week for odd number of teams
    
    n = len(teams)
    rounds = []
    
    # Generate round-robin schedule
    for round_num in range(n - 1):
        round_fixtures = []
        for i in range(n // 2):
            home = teams[i]
            away = teams[n - 1 - i]
            if home is not None and away is not None:
                round_fixtures.append((home, away))
        
        rounds.append(round_fixtures)
        
        # Rotate teams (except first)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    
    # Create fixtures in database
    base_date = league.start_date or datetime.utcnow()
    
    for round_idx, round_fixtures in enumerate(rounds):
        round_date = base_date + timedelta(days=round_idx * league.match_frequency)
        
        for home_id, away_id in round_fixtures:
            # Create home and away fixtures (double round-robin)
            # First leg
            fixture1 = Fixture(
                league_id=league.id,
                round=round_idx + 1,
                home_team_id=home_id,
                away_team_id=away_id,
                scheduled_date=round_date
            )
            db.session.add(fixture1)
            
            # Second leg (in second half of season)
            fixture2 = Fixture(
                league_id=league.id,
                round=round_idx + 1 + len(rounds),
                home_team_id=away_id,
                away_team_id=home_id,
                scheduled_date=round_date + timedelta(days=len(rounds) * league.match_frequency)
            )
            db.session.add(fixture2)