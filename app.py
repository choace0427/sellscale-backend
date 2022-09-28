import os
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

from src.setup.TimestampedModel import TimestampedModel
from flask_cors import CORS
from flask_migrate import Migrate

app = Flask(__name__)
cors = CORS(app)

app.config["CORS_HEADERS"] = "Content-Type"

app.config.from_object(os.environ["APP_SETTINGS"])
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(model_class=TimestampedModel)
migrate = Migrate(app, db)


from model_import import *


def register_blueprints(app):
    from src.echo.controllers import ECHO_BLUEPRINT
    from src.prospecting.controllers import PROSPECTING_BLUEPRINT
    from src.research.controllers import RESEARCH_BLUEPRINT
    from src.client.controllers import CLIENT_BLUEPRINT

    app.register_blueprint(ECHO_BLUEPRINT, url_prefix="/echo")
    app.register_blueprint(PROSPECTING_BLUEPRINT, url_prefix="/prospect")
    app.register_blueprint(RESEARCH_BLUEPRINT, url_prefix="/research")
    app.register_blueprint(CLIENT_BLUEPRINT, url_prefix="/client")

    db.init_app(app)


@app.route("/")
def hello():
    return "SellScale API."


register_blueprints(app)

if __name__ == "__main__":
    app.run()
