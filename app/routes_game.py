from flask import Blueprint, render_template, session, redirect, url_for

game_bp = Blueprint('game_bp', __name__)

@game_bp.route('/')
def index():
    # If user is already logged in, send them to their dashboard
    if 'username' in session:
        return redirect(url_for('game_bp.dashboard'))
    return render_template('index.html')

@game_bp.route('/dashboard')
def dashboard():
    # This route is protected; only logged-in users can see it
    if 'username' not in session:
        return redirect(url_for('auth_bp.login'))
    
    # Pass the username to the template
    return render_template('dashboard.html', username=session['username'])
