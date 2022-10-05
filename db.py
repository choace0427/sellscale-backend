from flask_sqlalchemy import SQLAlchemy
from src.setup.TimestampedModel import TimestampedModel


db = SQLAlchemy(model_class=TimestampedModel)
