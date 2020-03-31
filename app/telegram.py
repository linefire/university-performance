import time
from json import loads
from os import environ
from threading import Lock

from requests import post

from .model import ChildBot


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
def _send_message(bot_token: str, command: str, data: dict = None) -> dict:
    if data is None:
        data = {}
    response = post(f'https://api.telegram.org/bot{bot_token}/{command}', data)
    return loads(response.text)


def set_up_webhook(bot_token: str):
    project_name = environ['PROJECT_NAME']
    hook_url = f'https://{project_name}.herokuapp.com/webhook/{bot_token}'
    _send_message(bot_token, 'setWebhook', {'url': hook_url})


def send_message(bot_token: str, chat_id: int, text: str):
    _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': text,
    })


def check_bot_token(bot_token: str):
    response = _send_message(bot_token, 'getMe')
    return response['ok']


def set_up_webhooks():
    child_bots = ChildBot.query.all()
    child_bots.append(environ['TELEGRAM_TOKEN'])
    for child_bot in child_bots:
        set_up_webhook(child_bot)
