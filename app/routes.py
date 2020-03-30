from json import loads
from os import environ

from flask import request

from app import app
from app.telegram import send_message


def start(bot_token: str, data: dict):
    if bot_token == environ['TELEGRAM_TOKEN']:
        chat_id = data['message']['chat']['id']
        send_message(
            bot_token,
            chat_id,
            ('Привет, напиши сюда токен своего бота,'
             ' что бы передать нам управление'),
        )
    else:
        pass


@app.route('/webhook/<bot_token>', methods=['POST'])
def webhook(bot_token):
    data = loads(request.json)
    text = data['text']
    if text == '/start':
        start(bot_token)
    return ''
