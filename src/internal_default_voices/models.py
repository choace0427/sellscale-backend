from app import db
import sqlalchemy as sa


class InternalDefaultVoices(db.Model):
    __tablename__ = "internal_default_voices"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(4000), nullable=True)
    count_ctas = db.Column(db.Integer, nullable=True)
    count_bumps = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "count_ctas": self.count_ctas,
            "count_bumps": self.count_bumps,
        }
