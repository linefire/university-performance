from app import db


class ChildBot(db.Model):
    __tablename__ = 'child_bots'

    id = db.Column(db.Integer, primary_key=True)
    admin = db.Column(db.Integer)
    token = db.Column(db.String, unique=True)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    tg_id = db.Column(db.Integer)
    bot_id = db.Column(db.Integer, db.ForeignKey('child_bots.id'))
    menu = db.Column(db.String)


class Menu(db.Model):
    __tablename__ = 'menus'

    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('child_bots.id'))
    name = db.Column(db.String)
    description = db.Column(db.String)
    buttons = db.relationship('Button', backref='menus')


class Button(db.Model):
    __tablename__ = 'buttons'

    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'))
    text = db.Column(db.String)
    action_type = db.Column(db.String)
    action_id = db.Column(db.Integer)


class Action(db.Model):
    __tablename__ = 'actions'

    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('child_bots.id'))
    action_id = db.Column(db.String)
    order = db.Column(db.Integer)
    text = db.Column(db.String)
