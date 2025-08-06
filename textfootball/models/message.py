# textfootball/models/message.py

from textfootball import db
import datetime as std_datetime

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=std_datetime.datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    challenger_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    challenged_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    is_challenge = db.Column(db.Boolean, default=False)
    is_accepted = db.Column(db.Boolean, default=False)
