from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from app import db
from .models import User

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if user already exists in the database
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.')
            return redirect(url_for('auth_bp.register'))
        
        # Create a new user object
        new_user = User(username=username)
        new_user.set_password(password)
        
        # Add the new user to the database
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.')
        return redirect(url_for('auth_bp.login'))

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Find the user in the database
        user = User.query.filter_by(username=username).first()

        # Check if user exists and the password is correct
        if user and user.check_password(password):
            session['username'] = username
            return redirect(url_for('game_bp.dashboard'))
        else:
            flash('Invalid username or password.')
            return redirect(url_for('auth_bp.login'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('game_bp.index'))
