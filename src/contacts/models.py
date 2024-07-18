from app import db


class SavedApolloQuery(db.Model):
    __tablename__ = "saved_apollo_query"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    custom_name = db.Column(db.String, nullable=True)
    name_query = db.Column(db.String, nullable=False)
    data = db.Column(db.JSON, nullable=False)
    results = db.Column(db.JSON, nullable=True)
    is_prefilter = db.Column(db.Boolean, nullable=True)
    num_results = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "custom_name": self.custom_name,
            "client_sdr_id": self.client_sdr_id,
            "name_query": self.name_query,
            "data": self.data,
            "results": self.results,
            "is_prefilter": self.is_prefilter,
            "num_results": self.num_results,
        }
