from app import db


class SavedApolloQuery(db.Model):
    __tablename__ = "saved_apollo_query"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    name_query = db.Column(db.String, nullable=False)
    data = db.Column(db.JSON, nullable=False)
    is_prefilter = db.Column(db.Boolean, nullable=True)
    num_results = db.Column(db.Integer, nullable=True)
