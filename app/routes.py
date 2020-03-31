from json import loads
from os import environ
from re import match

from flask import request

from app import app, db
from .model import ChildBot
from app.telegram import send_message, check_bot_token, set_up_webhook


def get_control_bot(bot_token: str):
    child_bot = ChildBot()
    child_bot.admin = request.json['message']['from']['id']
    child_bot.token = bot_token
    db.session.add(child_bot)
    db.session.commit()

    set_up_webhook(bot_token)

    chat_id = request.json['message']['chat']['id']
    send_message(
        environ['TELEGRAM_TOKEN'],
        chat_id,
        'Теперь мы управляем Вашим ботом',
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
            pass
        else:
            send_message(
                bot_token,
                request.json['message']['chat']['id'],
                text,
            )
    return ''
