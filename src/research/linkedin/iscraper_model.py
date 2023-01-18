import requests
import json
from model_import import ResearchPayload, ResearchType
from src.utils.abstract.attr_utils import deep_get


class IScraperExtractorTransformer:
    def __init__(self, prospect_id):
        self.prospect_id = prospect_id
        payload = ResearchPayload.get_by_prospect_id(
            prospect_id, ResearchType.LINKEDIN_ISCRAPER
        )
        self.payload = {}
        if payload:
            self.payload = payload.payload

    def get_payload(self):
        """Get's the payload"""
        return self.payload

    def get_personal_payload(self):
        """Get's the personal payload from the payload"""
        return self.payload.get("personal")

    def get_company_payload(self):
        """Get's the company payload from the payload"""
        return self.payload.get("company")

    def get_slug(self):
        """Get's the linkedin slug from the payload"""
        return deep_get(self.payload, "personal.profile_id")

    def get_company_logo(self):
        """Get's the company logo from the payload"""
        return deep_get(self.payload, "company.details.images.logo")

    def get_company_name(self):
        """Get's the company name from the payload"""
        return deep_get(self.payload, "company.details.name")

    def get_company_location(self):
        """Get's the company location from the payload"""
        city = deep_get(self.payload, "company.details.locations.headquarter.city")
        geographic_area = deep_get(
            self.payload, "company.details.locations.headquarter.geographicArea"
        )
        return f"{city}, {geographic_area}"

    def get_company_headline(self):
        """Get's the company headline from the payload"""
        return deep_get(self.payload, "company.details.urls.company_page")

    def get_company_tags(self):
        """Get's the company tags from the payload"""
        return deep_get(self.payload, "company.details.specialities")

    def get_company_staff_count(self):
        """Get's the company staff count from the payload"""
        return deep_get(self.payload, "company.details.staff.total")
