from json import loads
from os import environ
from re import match

from flask import request
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.model import ChildBot, User
from app.telegram import send_message, check_bot_token, set_up_webhook, send_settings_menu


def get_control_bot(bot_token: str):
    child_bot = ChildBot()
    child_bot.admin = request.json['message']['from']['id']
    child_bot.token = bot_token
    db.session.add(child_bot)
    try:
        db.session.commit()

        set_up_webhook(bot_token)

        chat_id = request.json['message']['chat']['id']
        send_message(
            environ['TELEGRAM_TOKEN'],
            chat_id,
            'Теперь мы управляем Вашим ботом',
        )
    except IntegrityError:
        chat_id = request.json['message']['chat']['id']
        send_message(
            environ['TELEGRAM_TOKEN'],
            chat_id,
            'Мы уже управляем Вашим ботом',
        )


def check_token(text: str) -> bool:
    result = match(r'\d+:.+', text)
    if result:
        return check_bot_token(text)
    else:
        return False


def start_admin(bot_token: str):
    chat_id = request.json['message']['chat']['id']
    send_message(
        bot_token,
        chat_id,
        ('Привет, напиши сюда токен своего бота,'
         ' что бы передать нам управление'),
    )


def check_access_settings(bot_token: str) -> bool:
    user_id = request.json['message']['from']['id']
    bot = ChildBot.query.filter(ChildBot.token == bot_token).first()
    if bot.admin != user_id:
        return False

    user = User.query.filter(
        User.tg_id == user_id,
        User.bot_id == bot.id,
    ).first()
    if user.menu != 'start_menu':
        return False

    return True


@app.route('/webhook/<bot_token>', methods=['POST'])
def webhook(bot_token: str):
    text = request.json['message']['text']
    if bot_token == environ['TELEGRAM_TOKEN']:
        if text == '/start':
            start_admin(bot_token)
        if check_bot_token(text):
            get_control_bot(text)
    else:
        if text == '/start':
            send_message(
                bot_token,
                request.json['message']['chat']['id'],
                user_id=request.json['message']['from']['id'],
            )
        elif text == 'Настройки':
            if check_access_settings(bot_token):
                send_settings_menu(bot_token, request.json['message']['chat']['id'])
    return ''
