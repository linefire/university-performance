from os import environ

from requests import post


def _send_message(bot_token: str, command: str, data: dict):
    post(f'https://api.telegram.org/bot{bot_token}/{command}', data)


def set_up_webhook(bot_token: str):
    project_name = environ['PROJECT_NAME']
    hook_url = f'https://{project_name}.herokuapp.com/webhook/{bot_token}'
    _send_message(bot_token, 'setWebhook', {'url': hook_url})


def send_message(bot_token: str, chat_id: int, text: str):
    _send_message(bot_token, 'sendMessage', {
        'chat_id': chat_id,
        'text': text,
    })
