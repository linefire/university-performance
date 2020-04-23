from typing import Optional
from typing import Union

from app import db


class ChildBot(db.Model):
    __tablename__ = 'child_bots'

    id = db.Column(db.Integer, primary_key=True)
    admin = db.Column(db.Integer)
    token = db.Column(db.String, unique=True)

    @classmethod
    def get_by_token(cls, token: str) -> Optional['ChildBot']:
        return cls.query.filter(cls.token == token).first()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    tg_id = db.Column(db.Integer)
    bot_id = db.Column(db.Integer, db.ForeignKey('child_bots.id'))
    menu_path = db.Column(db.String)

    @classmethod
    def get_user(cls, bot_pointer: Union[int, str],
                 user_id: int) -> Optional['User']:
        if isinstance(bot_pointer, str):
            bot_pointer = ChildBot.get_by_token(bot_pointer).id

        return cls.query.filter(
            cls.tg_id == user_id,
            cls.bot_id == bot_pointer,
        ).first()


class Menu(db.Model):
    __tablename__ = 'menus'

    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('child_bots.id'))
    name = db.Column(db.String)
    description = db.Column(db.String)
    buttons = db.relationship('Button', backref='menus')

    @classmethod
    def get_menu(cls, bot_id: int, name: str) -> Optional['Menu']:
        return cls.query.filter(
            cls.bot_id == bot_id,
            cls.name == name,
        ).first()


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
