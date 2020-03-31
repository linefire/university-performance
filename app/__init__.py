from os import environ

from flask import Flask
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from flask_sqlalchemy import SQLAlchemy

from app.telegram import set_up_webhooks

TELEGRAM_TOKEN = environ['TELEGRAM_TOKEN']
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = environ['DATABASE_URL']
db = SQLAlchemy(app)
migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

from . import model
from . import routes

if __name__ == "__main__":
    manager.run()
else:
    set_up_webhooks()
