from os import environ
from re import match

from flask import request
from sqlalchemy.exc import IntegrityError

from app import app
from app import db
from app.model import ChildBot
from app.model import User
from app.telegram import add_button
from app.telegram import add_menu
from app.telegram import add_new_action
from app.telegram import add_subaction
from app.telegram import button_click
from app.telegram import send_actions_settings_menu
from app.telegram import send_add_action
from app.telegram import send_add_button_menu
from app.telegram import send_add_menu_menu
from app.telegram import send_edit_action_menu
from app.telegram import send_edit_menu
from app.telegram import send_menu_settings
from app.telegram import send_message
from app.telegram import check_bot_token
from app.telegram import set_up_webhook
from app.telegram import send_settings_menu
from app.telegram import send_previous_menu
from app.telegram import send_start_message


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
        db.session.rollback()


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


def check_access_settings(bot_token: str, user_id: int) -> bool:
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return False

    user = User.get_user(bot.id, user_id)
    if user.menu_path != '_start_menu':
        return False

    return True


@app.route('/webhook/<bot_token>', methods=['POST'])
def webhook(bot_token: str):
    print(request.json)
    try:
        text = request.json['message']['text']
    except KeyError:
        return ''
    chat_id = request.json['message']['chat']['id']
    user_id = request.json['message']['from']['id']
    if bot_token == environ['TELEGRAM_TOKEN']:
        if text == '/start':
            start_admin(bot_token)
        if check_bot_token(text):
            get_control_bot(text)
    else:
        user = User.get_user(bot_token, user_id)
        if text == '/start':
            send_start_message(bot_token, chat_id, user_id)
        elif text == 'Настройки':
            if check_access_settings(bot_token, user_id):
                send_settings_menu(bot_token, chat_id, user_id)
        elif text == 'Настройки меню':
            send_menu_settings(bot_token, chat_id, user_id)
        elif text == 'Добавить меню':
            send_add_menu_menu(bot_token, chat_id, user_id)
        elif text == 'Назад':
            send_previous_menu(bot_token, chat_id, user_id)
        elif user.menu_path == '_start_menu/_settings/_menus/_add_menu':
            add_menu(bot_token, chat_id, user_id, text)
        elif user.menu_path == '_start_menu/_settings/_menus' and \
                text.split()[0] == 'Редактировать' and \
                text.split()[2] == 'меню':
            send_edit_menu(bot_token, chat_id, user_id, text)
        elif user.menu_path.startswith('_start_menu/_settings/_menus/') and \
                text == 'Добавить кнопку':
            send_add_button_menu(bot_token, chat_id, user_id)
        elif user.menu_path.startswith('_start_menu/_settings/_menus/') and \
                user.menu_path.split('/')[-1] == '_add_button':
            add_button(bot_token, chat_id, user_id, text)
        elif user.menu_path == '_start_menu/_settings' and \
                text == 'Настройки действий':
            send_actions_settings_menu(bot_token, chat_id, user_id)
        elif user.menu_path == '_start_menu/_settings/_actions' and \
                text == 'Добавить действие':
            send_add_action(bot_token, chat_id, user_id)
        elif user.menu_path == '_start_menu/_settings/_actions/_add_action':
            add_new_action(bot_token, chat_id, user_id, text)
        elif user.menu_path == '_start_menu/_settings/_actions':
            send_edit_action_menu(bot_token, chat_id, user_id, text)
        elif user.menu_path.startswith('_start_menu/_settings/_actions/'):
            add_subaction(bot_token, chat_id, user_id, text)
        else:
            button_click(bot_token, chat_id, user_id, text)
    return ''
