import time
from json import dumps
from os import environ
from re import search
from threading import Lock
from typing import Union

from requests import post

from app import db
from app.model import Action
from app.model import Button
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


def check_bot_token(bot_token: str) -> bool:
    response = _send_message(bot_token, 'getMe')
    return response['ok']


def set_up_webhooks():
    child_bots = ChildBot.query.all()
    child_bots.append(environ['TELEGRAM_TOKEN'])
    for child_bot in child_bots:
        set_up_webhook(child_bot)


def _get_reply_markup(bot_token: str, menu_path: str,
                      is_admin: bool = False) -> (str, str):
    menu_name = menu_path.split('/')[-1]

    menu = Menu.get_menu(bot_token, menu_name)
    if menu_name == '_start_menu':
        desc = 'Главное меню'
    else:
        desc = menu.description

    keyboard = []
    for button in menu.buttons:
        keyboard.append([{'text': button.text}])

    if menu_path == '_start_menu':
        if is_admin:
            keyboard.append([{'text': 'Настройки'}])
    else:
        keyboard.append([{'text': 'Назад'}])

    data = {
        'resize_keyboard': True,
        'keyboard': keyboard,
    }

    return desc, dumps(data)


def send_start_message(bot_token: str, chat_id: int, user_id: int):
    bot = ChildBot.get_by_token(bot_token)
    user = User.get_user(bot.id, user_id)
    user.menu_path = '_start_menu'

    desc, reply = _get_reply_markup(bot_token, user.menu_path,
                                    bot.admin == user.tg_id)
    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': desc,
        'reply_markup': reply,
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def send_previous_menu(bot_token: str, chat_id: int, user_id: int):
    user = User.get_user(bot_token, user_id)
    if '/' not in user.menu_path:
        return

    menu_path = user.menu_path.split('/')[:-1]
    user.menu_path = '/'.join(menu_path)
    if menu_path[-1] == '_settings':
        response = _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'Настройки',
            'reply_markup': _get_settings_reply_markup(),
        })
    elif len(menu_path) and menu_path[-1] == '_menus':
        desc, repl = _get_menu_settings_reply_markup(bot_token)
        response = _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': desc,
            'reply_markup': repl,
        })
    elif len(menu_path) > 1 and menu_path[-2] == '_menus':
        desc, repl = _get_edit_menu_reply_markup(bot_token, menu_path[-1])
        response = _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': desc,
            'reply_markup': repl,
        })
    elif len(menu_path) and menu_path[-1] == '_actions':
        desc, reply = _get_actions_settings_menu_reply_markup(
            ChildBot.get_by_token(bot_token).id)
        response = _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': desc,
            'reply_markup': reply,
        })
    else:
        desc, reply = _get_reply_markup(bot_token, user.menu_path,
                                        ChildBot.get_by_token(
                                            bot_token).admin == user_id)
        response = _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': desc,
            'reply_markup': reply,
        })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def _get_settings_reply_markup() -> str:
    return dumps({
        'resize_keyboard': True,
        'keyboard': [
            [{'text': 'Настройки меню'}],
            [{'text': 'Настройки действий'}],
            [{'text': 'Назад'}],
        ],
    })


def button_click(bot_token: str, chat_id: int, user_id: int, text: str):
    user = User.get_user(bot_token, user_id)
    menu = Menu.query.filter(
        Menu.bot_id == ChildBot.get_by_token(bot_token).id,
        Menu.name == user.menu_path.split('/')[-1],
    ).first()
    if not menu:
        return

    button = Button.query.filter(
        Button.menu_id == menu.id,
        Button.text == text,
    ).first()
    if not button:
        return

    if button.action_type == 'm':
        user.menu_path += f'/{button.action_name}'
        desc, repl = _get_reply_markup(bot_token,
                                       user.menu_path,
                                       ChildBot.get_by_token(
                                           bot_token).admin == user_id)
        response = _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': desc,
            'reply_markup': repl,
        })

        if response['ok']:
            db.session.commit()
        else:
            db.session.rollback()
    elif button.action_type == 'a':
        start_action(bot_token, chat_id, button.action_name)


def send_settings_menu(bot_token: str, chat_id: int, user_id: int):
    user = User.get_user(bot_token, user_id)
    user.menu_path += '/_settings'

    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': 'Настройки',
        'reply_markup': _get_settings_reply_markup(),
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def _get_menu_settings_reply_markup(bot_pointer: Union[int, str]) -> (str,
                                                                      str):
    menus = Menu.get_menus(bot_pointer)

    keyboard = []
    for menu in menus:
        keyboard.append([{'text': f'Редактировать {menu.name} меню'}])

    keyboard.append([{'text': 'Добавить меню'}])
    keyboard.append([{'text': 'Назад'}])

    return 'Настройки меню', dumps({
        'resize_keyboard': True,
        'keyboard': keyboard,
    })


def send_menu_settings(bot_token: str, chat_id: int, user_id: int):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if not user.menu_path == '_start_menu/_settings':
        return

    user.menu_path += '/_menus'

    desc, repl = _get_menu_settings_reply_markup(bot.id)
    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': desc,
        'reply_markup': repl,
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def send_add_menu_menu(bot_token: str, chat_id: int, user_id: int):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if not user.menu_path == '_start_menu/_settings/_menus':
        return

    user.menu_path += '/_add_menu'

    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': ('Добавьте меню -> имя;описание меню\n'
                 'имя должно содержать только латинские буквы,\n'
                 'имя и описание должны быть разделены точкой с запятой.'),
        'reply_markup': dumps({
            'resize_keyboard': True,
            'keyboard': [
                [{'text': 'Назад'}],
            ],
        }),
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def add_menu(bot_token: str, chat_id: int, user_id: int, text: str):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if not user.menu_path == '_start_menu/_settings/_menus/_add_menu':
        return

    if ';' not in text:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'имя и описание должны быть разделены точкой с запятой.',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}],
                ],
            }),
        })
        return

    name = text[:text.index(';')].strip()
    desc = text[text.index(';') + 1:].strip()

    if search(r'[^a-zA-Z]', name):
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'имя должно быть написано латинскими буквами.',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}],
                ],
            }),
        })
        return

    if not desc:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'описание не может быть пустым.',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}],
                ],
            }),
        })
        return

    menu = Menu()
    menu.name = name
    menu.description = desc
    menu.bot_id = bot.id

    db.session.add(menu)
    db.session.commit()

    send_previous_menu(bot_token, chat_id, user_id)


def _get_edit_menu_reply_markup(bot_pointer: Union[int, str],
                                menu_name: str) -> (str, str):
    menu = Menu.get_menu(bot_pointer, menu_name)

    keyboard = []
    for button in menu.buttons:
        keyboard.append([{'text': button.text}])

    keyboard.append([{'text': 'Добавить кнопку'}])
    keyboard.append([{'text': 'Изменить порядок кнопок'}])
    keyboard.append([{'text': 'Назад'}])

    return f'Настройки {menu_name} меню', dumps({
        'resize_keyboard': True,
        'keyboard': keyboard,
    })


def send_edit_menu(bot_token: str, chat_id: int, user_id: int, text: str):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if user.menu_path != '_start_menu/_settings/_menus':
        return

    menu_name = text.split()[1]
    user.menu_path += f'/{menu_name}'

    desc, repl = _get_edit_menu_reply_markup(bot.id, menu_name)

    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': desc,
        'reply_markup': repl,
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def send_add_button_menu(bot_token: str, chat_id: int, user_id: int):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if not user.menu_path.startswith('_start_menu/_settings/_menus/'):
        return

    user.menu_path += '/_add_button'

    menus = Menu.get_menus(bot.id)
    actions = Action.get_actions(bot.id)

    text = ('Добавьте кнопку, напишите нам\n'
            '"текст кнопки;тип действия;название действия"\n'
            'тип действия должен быть a/m - действие/меню\n'
            'название действия должно быть выбрано из списка ниже\n'
            'Примеры:```\n'
            'button text;a;action_name\n'
            'button text;m;menu_name```\n')

    text += 'Ваши меню:\n'
    for menu in menus:
        text += f'{menu.name}\n'

    text += 'Ваши действия:\n'
    for action in actions:
        if action.order == 0:
            text += f'{action.name}\n'

    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': dumps({
            'resize_keyboard': True,
            'keyboard': [
                [{'text': 'Назад'}],
            ],
        }),
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def add_button(bot_token: str, chat_id: int, user_id: int, text: str):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if not user.menu_path.startswith('_start_menu/_settings/_menus/'):
        return

    try:
        button_text, type_button, type_name = text.split(';')
    except ValueError:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'Неправильно расставлены ";"',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}],
                ],
            }),
        })
        return

    if not button_text:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'Текст кнопки пустой',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}],
                ],
            }),
        })
        return

    if type_button not in ('a', 'm'):
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'Неправильно выбран тип действия используйте "a" или "m"',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}],
                ],
            }),
        })
        return

    menu_name = user.menu_path.split('/')[-2]

    menu = Menu.get_menu(bot.id, menu_name)

    if type_button == 'm':
        menu2 = Menu.query.filter(
            Menu.bot_id == bot.id,
            Menu.name == type_name,
        ).first()

        if not menu2:
            _send_message(bot_token, 'sendMessage', {
                'chat_id': chat_id,
                'text': f'Меню {type_name} не существует',
                'reply_markup': dumps({
                    'resize_keyboard': True,
                    'keyboard': [
                        [{'text': 'Назад'}],
                    ],
                }),
            })
            return
    else:
        action = Action.query.filter(
            Action.bot_id == bot.id,
            Action.name == type_name,
        ).first()

        if not action:
            _send_message(bot_token, 'sendMessage', {
                'chat_id': chat_id,
                'text': f'Действия {type_name} не существует',
                'reply_markup': dumps({
                    'resize_keyboard': True,
                    'keyboard': [
                        [{'text': 'Назад'}],
                    ],
                }),
            })
            return

    button = Button()
    button.menu_id = menu.id
    button.text = button_text
    button.action_type = type_button
    button.action_name = type_name

    menu.buttons.append(button)

    db.session.commit()

    _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': 'Кнопка добавлена',
        'reply_markup': dumps({
            'resize_keyboard': True,
            'keyboard': [
                [{'text': 'Назад'}],
            ],
        }),
    })

    send_previous_menu(bot_token, chat_id, user_id)


def _get_actions_settings_menu_reply_markup(bot_id: int) -> (str, str):
    keyboard = []
    buttons = db.session.query(Action.name).distinct().filter(
        Action.bot_id == bot_id).all()

    for button in buttons:
        keyboard.append([{'text': button.name}])

    keyboard.extend([
        [{'text': 'Добавить действие'}],
        [{'text': 'Удалить действие'}],
        [{'text': 'Назад'}],
    ])

    return 'Настройки действий', dumps({
        'resize_keyboard': True,
        'keyboard': keyboard,
    })


def send_actions_settings_menu(bot_token: str, chat_id: int, user_id: int):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if user.menu_path != '_start_menu/_settings':
        return

    user.menu_path += '/_actions'

    desc, repl = _get_actions_settings_menu_reply_markup(bot.id)
    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': desc,
        'reply_markup': repl,
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def send_add_action(bot_token: str, chat_id: int, user_id: int):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if user.menu_path != '_start_menu/_settings/_actions':
        return

    user.menu_path += '/_add_action'

    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': ('Добавить действие\n'
                 'назовите действие латинскими буквами и описание\n'
                 'Пример: название действия;описание'),
        'reply_markup': dumps({
            'resize_keyboard': True,
            'keyboard': [
                [{'text': 'Назад'}]
            ],
        }),
    })

    if response['ok']:
        db.session.commit()
    else:
        db.session.rollback()


def add_new_action(bot_token: str, chat_id: int, user_id: int, text: str):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if user.menu_path != '_start_menu/_settings/_actions/_add_action':
        return

    name = text[:text.index(';')].strip()
    desc = text[text.index(';') + 1:].strip()
    if search(r'[^a-zA-Z]', name):
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'Название должно быть написано латинскими буквами',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}]
                ],
            }),
        })
        return

    if not desc:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': 'Описание не может быть пустым',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}]
                ],
            }),
        })
        return

    action = Action.query.filter(
        Action.bot_id == bot.id,
        Action.name == name,
    ).first()

    if action:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': f'Действие {name} уже существует',
            'reply_markup': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}]
                ],
            }),
        })
        return

    action = Action()
    action.bot_id = bot.id
    action.name = name
    action.order = 0
    action.text = desc

    db.session.add(action)

    user.menu_path = '/'.join(user.menu_path.split('/')[:-1])
    send_edit_action_menu(bot_token, chat_id, user_id, name)
    db.session.commit()


def send_edit_action_menu(bot_token: str, chat_id: int,
                          user_id: int, text: str):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if user.menu_path != '_start_menu/_settings/_actions':
        return

    action = Action.query.filter(
        Action.bot_id == bot.id,
        Action.name == text,
    ).first()

    if not action:
        return

    user.menu_path += f'/{text}'

    response = _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': ('Напишите какие сообщения буду посылаться клиенту '
                 'при вызове действия, мы уже записываем.'),
        'reply_markup': dumps([
            [{'text': 'Назад'}],
        ]),
    })


def add_subaction(bot_token: str, chat_id: int, user_id: int, text: str):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if user.menu_path.startswith('_start_menu/_settings/_actions/'):
        return

    text = text.strip()
    if not text:
        return
    action = Action()
    action.name = user.menu_path.split('/')[-1]
    action.text = text
    action.order = len(Action.query.filter(Action.bot_id == bot.id,
                                           Action.name == action.name).all())
    action.bot_id = bot.id

    db.session.add(action)
    db.session.commit()


def delete_action(bot_token: str, chat_id: int, user_id: int, text: str):
    bot = ChildBot.get_by_token(bot_token)
    if bot.admin != user_id:
        return

    user = User.get_user(bot.id, user_id)
    if user.menu_path != '_start_menu/_settings/_actions':
        return

    text = text.strip()
    actions = Action.query.filter(Action.name == text,
                                  Action.bot_id == bot.id).all()

    if not actions:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': f'Действия с названием {text} не существует',
            'reply_keyboard': dumps({
                'resize_keyboard': True,
                'keyboard': [
                    [{'text': 'Назад'}],
                ],
            }),
        })
        return

    for action in actions:
        db.session.remove(action)

    db.session.commit()


def start_action(bot_token: str, chat_id: int, action_name: str):
    actions = Action.query.filter(
        Action.bot_id == ChildBot.get_by_token(bot_token).id,
        Action.name == action_name,
    ).order_by(Action.order).all()

    for action in actions:
        _send_message(bot_token, 'sendMessage', {
            'chat_id': chat_id,
            'text': action.text,
        })


def send_message(bot_token: str, chat_id: int, text: str):
    _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': text,
    })
