# textfootball/blueprints/auth/routes.py (Corrected)

from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from textfootball import db
from textfootball.models import User # Use absolute import from the package root

# The name 'auth' here is used in url_for(), e.g., url_for('auth.login')
auth_bp = Blueprint('auth', __name__) 

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # This code does not need to change
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'danger')
            return redirect(url_for('auth.register'))
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        session['username'] = username
        flash('Registration successful! You are now logged in.', 'success')
        return redirect(url_for('game.dashboard'))
    
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # This code does not need to change
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('game.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    # This code does not need to change
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('game.index'))
