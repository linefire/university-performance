import time
from json import dumps
from os import environ
from threading import Lock
from typing import List, Dict, Tuple

from flask import request
from requests import post

from app import db
from app.model import ChildBot, Menu, User


def _limit_calls_per_second(count: int):
    lock = Lock()
    min_interval = 1.0 / float(count)

    def decorate(func):
        last_time_called = time.perf_counter()

        def limited_func(*args, **kwargs):
            lock.acquire()
            nonlocal last_time_called
            try:
                elapsed = time.perf_counter() - last_time_called
                left_to_wait = min_interval - elapsed

                if left_to_wait > 0:
                    time.sleep(left_to_wait)
                return func(*args, **kwargs)
            finally:
                last_time_called = time.perf_counter()
                lock.release()
        return limited_func
    return decorate


@_limit_calls_per_second(30)
def _send_message(bot_token: str,
                  command: str, data: dict = None) -> dict:
    if data is None:
        data = {}
    response = post(
        f'https://api.telegram.org/bot{bot_token}/{command}',
        data,
    )
    data = response.json()
    if not data['ok']:
        print(data)
    return data


def set_up_webhook(bot_token: str):
    project_name = environ['PROJECT_NAME']
    hook_url = f'https://{project_name}.herokuapp.com/webhook/{bot_token}'
    _send_message(bot_token, 'setWebhook', {'url': hook_url})


def _get_menu(bot_token: str,
              user_id: int) -> Tuple[str, List[List[Dict[str, str]]]]:
    reply_markup = []

    bot = ChildBot.query.filter(
        ChildBot.token == bot_token,
    ).first()

    if not bot:
        return '', reply_markup

    user = User.query.filter(
        User.tg_id == user_id,
        User.bot_id == bot.id,
    ).first()

    if not user:
        user = User()
        user.tg_id = user_id,
        user.bot_id = bot.id,

        menu = Menu.query.filter(
            Menu.bot_id == bot.id,
            Menu.name == 'start_menu',
        ).first()

        if not menu:
            menu = Menu()
            menu.bot_id = bot.id
            menu.name = 'start_menu'
            menu.description = 'Главное меню'

            db.session.add(menu)
            db.session.flush()
            db.session.refresh(menu)

        user.menu = menu.name

        db.session.add(user)
        db.session.commit()

    menu = Menu.query.filter(
        Menu.bot_id == bot.id,
        Menu.name == user.menu.split('/')[-1],
    ).first()

    for button in menu.buttons:
        reply_markup.append([{'text': button.text}])

    is_admin = bot.admin == user.tg_id

    if is_admin:
        reply_markup.append([{'text': 'Настройки'}])

    return menu.description, reply_markup


def send_message(bot_token: str, chat_id: int,
                 text: str = None, user_id: int = None):
    data = {'chat_id': chat_id}

    if text is not None:
        data['text'] = text

    if user_id:
        menu_desc, keyboard = _get_menu(bot_token, user_id)
        if keyboard:
            data['reply_markup'] = dumps({
                'keyboard': keyboard,
                'resize_keyboard': True,
            })
        if not data.get('text'):
            data['text'] = menu_desc

    print(data)

    if data.get('text'):
        _send_message(bot_token, 'sendMessage', data)


def send_settings_menu(bot_token: str, chat_id: int):
    data = {
        'chat_id': chat_id,
        'text': 'Ваши настройки',
        'reply_markup': dumps({
            'resize_keyboard': True,
            'keyboard': [
                [{'text': 'Редактор меню'}],
                [{'text': 'Редактор действий'}],
                [{'text': 'Назад'}],
            ]
        })
    }

    response = _send_message(bot_token, 'sendMessage', data)
    print(response)
    if response['ok']:
        user = User.query.filter(
            User.bot_id == ChildBot.query.filter(
                ChildBot.token == bot_token).first().id,
            User.tg_id == request.json['message']['from']['id'],
        ).first()
        user.menu += '/settings'
        db.session.commit()


def send_previous_menu(bot_token: str, chat_id: int, user_id: int):
    user = User.query.filter(
        User.tg_id == user_id,
        User.bot_id == ChildBot.query.filter(ChildBot.token == bot_token).first().id,
    ).first()

    user_path = user.menu.split('/')
    user.menu = '/'.join(user_path[:-1])
    if user_path[-2] == 'start_menu':
        send_message(bot_token, chat_id, user_id=user_id)
    elif user_path[-2] == 'settings':
        send_settings_menu(bot_token, chat_id)


def check_bot_token(bot_token: str) -> bool:
    response = _send_message(bot_token, 'getMe')
    return response['ok']


def set_up_webhooks():
    child_bots = ChildBot.query.all()
    child_bots.append(environ['TELEGRAM_TOKEN'])
    for child_bot in child_bots:
        set_up_webhook(child_bot)
