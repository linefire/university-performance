from flask import request

from app import app


@app.route('/webhook/<bot_token>', method='POST')
def webhook(bot_token):
    print(str(request))
    print(bot_token, request.json)
