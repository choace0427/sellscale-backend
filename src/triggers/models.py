from app import db
from enum import Enum
from typing import TypedDict

import jsonpickle

from src.client.models import ClientArchetype


class TriggerType(Enum):
    RECURRING_PROSPECT_SCRAPE = "recurring_prospect_scrape"
    NEWS_EVENT = "news_event"


class Trigger(db.Model):
    __tablename__ = "trigger"

    id = db.Column(db.Integer, primary_key=True)

    emoji = db.Column(db.String, nullable=False, default="⚡️")
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)

    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    interval_in_minutes = db.Column(db.Integer, nullable=True)

    # Deprecated
    trigger_type = db.Column(db.Enum(TriggerType), nullable=True)
    trigger_config = db.Column(db.JSON, nullable=False, default={})
    #

    blocks = db.Column(db.ARRAY(db.JSON), nullable=True)

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    active = db.Column(db.Boolean, nullable=False, default=True)

    keyword_blacklist = db.Column(db.JSON, nullable=True)

    def to_dict(self, include_rich_info: bool = False):
        retval = {
            "id": self.id,
            "emoji": self.emoji,
            "name": self.name,
            "description": self.description,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "interval_in_minutes": self.interval_in_minutes,
            "trigger_type": self.trigger_type.value,
            "trigger_config": self.trigger_config,
            "client_archetype_id": self.client_archetype_id,
            "active": self.active,
            "blocks": [block.to_dict() for block in convertDictToBlocks(self.blocks or [])],
            "keyword_blacklist": self.keyword_blacklist,
        }

        if include_rich_info:
            archetype: ClientArchetype = ClientArchetype.query.get(
                self.client_archetype_id
            )
            if archetype:
                retval["client_archetype"] = archetype.to_dict()

            num_prospects_scraped = (
                TriggerProspect.query.join(TriggerRun)
                .filter(TriggerRun.trigger_id == self.id)
                .all()
            )
            retval["num_prospects_scraped"] = len(num_prospects_scraped)
            retval["num_prospect_companies"] = len(
                list(set([prospect.company for prospect in num_prospects_scraped]))
            )

        return retval


class TriggerRun(db.Model):
    __tablename__ = "trigger_run"

    id = db.Column(db.Integer, primary_key=True)

    trigger_id = db.Column(db.Integer, db.ForeignKey("trigger.id"), nullable=False)
    trigger = db.relationship("Trigger", backref="trigger_runs")

    run_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    run_status = db.Column(db.String, nullable=False)
    run_message = db.Column(db.String, nullable=True)

    def to_dict(self):
        prospects_found = TriggerProspect.query.filter_by(trigger_run_id=self.id).all()

        return {
            "id": self.id,
            "trigger_id": self.trigger_id,
            "run_at": self.run_at,
            "run_status": self.run_status,
            "run_message": self.run_message,
            "num_prospects": len(prospects_found),
            "companies": list(set([prospect.company for prospect in prospects_found])),
        }


class TriggerProspect(db.Model):
    __tablename__ = "trigger_prospect"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    company = db.Column(db.String, nullable=True)
    linkedin_url = db.Column(db.String, nullable=True)
    custom_data = db.Column(db.String, nullable=True)

    trigger_run_id = db.Column(
        db.Integer, db.ForeignKey("trigger_run.id"), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "title": self.title,
            "company": self.company,
            "linkedin_url": self.linkedin_url,
            "custom_data": self.custom_data,
        }


# Trigger Blocks #

MetaDataRecord = Enum(
    "MetaDataRecord",
    [
        "SOURCE_PROSPECTS_FOUND",
        "SOURCE_COMPANIES_FOUND",
        "SOURCE_COMPANY_TYPE",
        "SOURCE_COMPANY_QUERY",
        "CURRENT_PROSPECTS_FOUND",
        "CURRENT_COMPANIES_FOUND",
        "PROSPECTS_UPLOADED",
    ],
)

BlockType = Enum("BlockType", ["SOURCE", "FILTER", "ACTION"])
SourceType = Enum(
    "SourceType", ["GOOGLE_COMPANY_NEWS", "EXTRACT_PROSPECTS_FROM_COMPANIES"]
)
ActionType = Enum("ActionType", ["SEND_SLACK_MESSAGE", "UPLOAD_PROSPECTS"])


class CustomDataDict(TypedDict):
    key: str
    value: str


class PipelineProspect:
    def __init__(
        self,
        first_name: str,
        last_name: str,
        title: str,
        company: str,
        linkedin_url: str,
        custom_data: CustomDataDict,
    ):
        self.first_name = first_name
        self.last_name = last_name
        self.title = title
        self.company = company
        self.linkedin_url = linkedin_url
        self.custom_data = custom_data

    def to_dict(self):
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "title": self.title,
            "company": self.company,
            "linkedin_url": self.linkedin_url,
            "custom_data": self.custom_data,
        }


class PipelineCompany:
    def __init__(
        self,
        img_url: str,
        article_title: str,
        article_snippet: str,
        article_link: str,
        article_date: str,
        company_name: str,
    ):
        self.img_url = img_url
        self.article_title = article_title
        self.article_snippet = article_snippet
        self.article_link = article_link
        self.article_date = article_date
        self.company_name = company_name

    def to_dict(self):
        return {
            "img_url": self.img_url,
            "article_title": self.article_title,
            "article_snippet": self.article_snippet,
            "article_link": self.article_link,
            "article_date": self.article_date,
            "company_name": self.company_name,
        }


class FilterCriteria:
    def __init__(
        self,
        prospect_titles: list[str] = [],
        company_names: list[str] = [],
        article_titles: list[str] = [],
        article_snippets: list[str] = [],
        prospect_query: str = "",
        company_query: str = "",
    ):
        self.prospect_titles = prospect_titles
        self.company_names = company_names
        self.article_titles = article_titles
        self.article_snippets = article_snippets
        self.prospect_query = prospect_query
        self.company_query = company_query

    def to_dict(self):
        return {
            "prospect_titles": self.prospect_titles,
            "company_names": self.company_names,
            "article_titles": self.article_titles,
            "article_snippets": self.article_snippets,
            "prospect_query": self.prospect_query,
            "company_query": self.company_query,
        }


class PipelineData:
    def __init__(
        self,
        prospects: list[PipelineProspect],
        companies: list[PipelineCompany],
        meta_data: CustomDataDict,
    ):
        self.prospects = prospects
        self.companies = companies
        self.meta_data = meta_data

    def to_dict(self):
        return {
            "prospects": [prospect.to_dict() for prospect in self.prospects],
            "companies": [company.to_dict() for company in self.companies],
            "meta_data": self.meta_data,
        }


class Block:
    def __init__(self, type: BlockType):
        self.type = type

    def to_dict(self):
        return {
            "type": self.type.name,
        }


class SourceBlock(Block):
    def __init__(self, source: SourceType, data: CustomDataDict):
        super().__init__(BlockType.SOURCE)
        self.source = source
        self.data = data

    def to_dict(self):
        return {
            "type": self.type.name,
            "source": self.source.name,
            "data": self.data,
        }


class FilterBlock(Block):
    def __init__(self, criteria: FilterCriteria):
        super().__init__(BlockType.FILTER)
        self.criteria = criteria

    def to_dict(self):
        return {
            "type": self.type.name,
            "criteria": self.criteria.to_dict(),
        }


class ActionBlock(Block):
    def __init__(self, action: ActionType, data: CustomDataDict):
        super().__init__(BlockType.ACTION)
        self.action = action
        self.data = data

    def to_dict(self):
        return {
            "type": self.type.name,
            "action": self.action.name,
            "data": self.data,
        }


def convertBlocksToDict(blocks: list[Block]):
    return [jsonpickle.encode(block) for block in blocks]


def convertDictToBlocks(blocks: list[dict]) -> list[Block]:
    return [jsonpickle.decode(block) for block in blocks]


def get_blocks_from_output_dict(blocks: list[dict]) -> list[Block]:
    output = []
    for block in blocks:
        if block.get('type') == "SOURCE":
            output.append(SourceBlock(SourceType[block.get('source')], block.get('data')))
        elif block.get('type') == "FILTER":
            output.append(FilterBlock(FilterCriteria(**block.get('criteria'))))
        elif block.get('type') == "ACTION":
            output.append(ActionBlock(ActionType[block.get('action')], block.get('data')))
    return output
    
    
