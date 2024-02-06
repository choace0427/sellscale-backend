def get_custom_research(prospect_id: int, data: dict) -> dict:
    return {"response": data.get("custom", "")}
