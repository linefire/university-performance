from json import loads
from os import environ

from flask import request

from app import app
from app.telegram import send_message


def start(bot_token: str):
    if bot_token == environ['TELEGRAM_TOKEN']:
        chat_id = request.json['message']['chat']['id']
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
    text = request.json['message']['text']
    if text == '/start':
        start(bot_token)
    return ''
