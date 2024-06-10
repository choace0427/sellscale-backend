from typing import TypedDict, Union


class Organization(TypedDict):
    id: str
    name: str


class Owner(TypedDict):
    id: str


class AccountData(TypedDict):
    id: str
    name: str
    owner: Owner
    domain: str
    type: str
    created_at: str


class User(TypedDict):
    id: str
    name: str
    email: str


class Issue(TypedDict):
    id: str
    number: int
    title: str
    body_html: str
    state: str
    account: AccountData
    assignee: Union[dict, None]  # This has a type, not sure what it is yet
    requester: Union[dict, None]  # This has a type, not sure what it is yet
    team: Union[dict, None]  # This has a type, not sure what it is yet
    tags: list[dict]  # This has a specific type in the list, not sure what it is yet
    custom_fields: dict  # This has a specific type, not sure what it is yet
    created_at: str
