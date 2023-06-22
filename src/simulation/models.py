
from app import db
from src.prospecting.models import Prospect
import enum


class SimulationType(enum.Enum):
    LI_CONVERSATION = "LI_CONVERSATION"
    EMAIL_CONVERSATION = "EMAIL_CONVERSATION"


class Simulation(db.Model):
    __tablename__ = "simulation"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"), nullable=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=True)

    type = db.Column(db.Enum(SimulationType), nullable=False)
    
    meta_data = db.Column(db.JSON, nullable=True)
    """ For LI_CONVERSATION:
    {
      "overall_status": ProspectOverallStatus | None,
      "li_status": ProspectStatus | None,
      "email_status": ProspectEmailOutreachStatus | None,
      "bump_count": int | None,
    }
    """

    def to_dict(self) -> dict:
        
        if self.prospect_id:
          prospect = Prospect.query.get(self.prospect_id)
        else:
          prospect = None

        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "archetype_id": self.archetype_id,
            "prospect_id": self.prospect_id,
            "prospect": prospect.to_dict() if prospect else None,
            "type": self.type.value,
            "meta_data": self.meta_data,
        }


class SimulationRecordType(enum.Enum):
   LI_CONVERSATION_MESSAGE = "LI_CONVERSATION_MESSAGE"
   EMAIL_CONVERSATION_MESSAGE = "EMAIL_CONVERSATION_MESSAGE"


class SimulationRecord(db.Model):
    __tablename__ = "simulation_record"

    id = db.Column(db.Integer, primary_key=True)

    simulation_id = db.Column(db.Integer, db.ForeignKey("simulation.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"), nullable=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=True)

    type = db.Column(db.Enum(SimulationRecordType), nullable=False)

    data = db.Column(db.JSON, nullable=False)
    """For LI_CONVERSATION_MESSAGE:
    {
      "author": str,
      "message": str,
      "connection_degree": 'You' | '1st',
      "li_id": int | None,
    }
    """

    meta_data = db.Column(db.JSON, nullable=True)

    def to_dict(self) -> dict:
        
        if self.prospect_id:
          prospect = Prospect.query.get(self.prospect_id)
        else:
          prospect = None

        return {
            "id": self.id,
            "simulation_id": self.simulation_id,
            "client_sdr_id": self.client_sdr_id,
            "archetype_id": self.archetype_id,
            "prospect_id": self.prospect_id,
            "prospect": prospect.to_dict() if prospect else None,
            "type": self.type.value,
            "data": self.data,
            "meta_data": self.meta_data,
        }