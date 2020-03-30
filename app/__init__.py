from os import environ

from flask import Flask

from app.telegram import set_up_webhook

TELEGRAM_TOKEN = environ['TELEGRAM_TOKEN']
app = Flask(__name__)

set_up_webhook(TELEGRAM_TOKEN)

from . import routes

if __name__ == "__main__":
    app.run()
