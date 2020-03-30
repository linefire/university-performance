from os import environ

from requests import post


def _send_message(command: str, data: dict):
    token = environ['TELEGRAM_TOKEN']
    response = post(f'https://api.telegram.org/bot{token}/{command}', data)


def set_up_webhook(bot_token: str):
    project_name = environ['PROJECT_NAME']
    hook_url = f'https://{project_name}.herokuapp.com/webhook/{bot_token}'
    _send_message('setWebhook', {'url': hook_url})
