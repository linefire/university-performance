from app import db


class ChildBot(db.Model):
    __tablename__ = 'child_bots'

    id = db.Column(db.Integer, primary_key=True)
    admin = db.Column(db.Integer)
    token = db.Column(db.String, unique=True)
