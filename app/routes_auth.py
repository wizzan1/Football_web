# app/routes_auth.py (updated to auto-login after successful registration)
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app import db
from .models import User

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
       
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'danger')
            return redirect(url_for('auth_bp.register'))
       
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
       
        # NEW: Auto-login after successful registration
        session['username'] = username
        flash('Registration successful! You are now logged in.', 'success')
        return redirect(url_for('game_bp.dashboard'))
   
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
       
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('game_bp.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth_bp.login'))
   
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('game_bp.index'))
