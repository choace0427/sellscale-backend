from flask_sqlalchemy import Model
from sqlalchemy import Column, DateTime
import datetime

class TimestampedModel(Model):
    created_at = Column(DateTime, default=datetime.datetime.now())
    updated_at = Column(DateTime, default=datetime.datetime.now(), onupdate=datetime.datetime.now())