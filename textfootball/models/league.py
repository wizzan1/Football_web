# textfootball/models/league.py

from textfootball import db
from datetime import datetime
import enum

class LeagueStatus(enum.Enum):
    RECRUITING = "recruiting"  # Open for teams to join
    READY = "ready"            # Full or manually started, generating fixtures
    ACTIVE = "active"          # Season in progress
    COMPLETED = "completed"    # Season finished

class League(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Privacy Settings
    is_public = db.Column(db.Boolean, default=True)
    password = db.Column(db.String(200))  # Will be hashed if private
    
    # League Configuration
    max_teams = db.Column(db.Integer, default=10)
    min_teams = db.Column(db.Integer, default=4)  # Minimum to start
    match_frequency = db.Column(db.Integer, default=3)  # Days between match rounds
    
    # Status & Progress
    status = db.Column(db.Enum(LeagueStatus), default=LeagueStatus.RECRUITING)
    season = db.Column(db.Integer, default=1)
    current_round = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime)  # When the season started
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[creator_id], backref='created_leagues')
    league_teams = db.relationship('LeagueTeam', backref='league', cascade='all, delete-orphan')
    fixtures = db.relationship('Fixture', backref='league', cascade='all, delete-orphan')
    
    @property
    def current_team_count(self):
        return len(self.league_teams)
    
    @property
    def is_full(self):
        return self.current_team_count >= self.max_teams
    
    @property
    def can_start(self):
        return self.current_team_count >= self.min_teams
    
    @property
    def spots_available(self):
        return self.max_teams - self.current_team_count

class LeagueTeam(db.Model):
    """Junction table linking teams to leagues with their stats"""
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    joined_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # League Statistics
    played = db.Column(db.Integer, default=0)
    won = db.Column(db.Integer, default=0)
    drawn = db.Column(db.Integer, default=0)
    lost = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    
    # Position tracking
    position = db.Column(db.Integer, default=0)  # Current league position
    
    # Relationships
    team = db.relationship('Team', backref='league_participations')
    
    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against
    
    @property
    def form(self):
        """Return last 5 match results as a string like 'WWLDW'"""
        # TODO: Implement when we have match history
        return ""

class Fixture(db.Model):
    """Represents a scheduled or played match in a league"""
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'), nullable=False)
    round = db.Column(db.Integer, nullable=False)
    
    # Teams
    home_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    
    # Scheduling
    scheduled_date = db.Column(db.DateTime)
    played_date = db.Column(db.DateTime)
    
    # Status
    is_played = db.Column(db.Boolean, default=False)
    
    # Results
    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    
    # Match details (link to match result if needed)
    match_result_id = db.Column(db.Integer)  # Can link to detailed match result later
    
    # Relationships
    home_team = db.relationship('Team', foreign_keys=[home_team_id], backref='home_fixtures')
    away_team = db.relationship('Team', foreign_keys=[away_team_id], backref='away_fixtures')
    
    @property
    def result_string(self):
        if not self.is_played:
            return "Not played"
        return f"{self.home_score} - {self.away_score}"