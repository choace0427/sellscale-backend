from model_import import LinkedinConversationEntry
from datetime import datetime
from app import db


def check_for_duplicate_linkedin_conversation_entry(
    conversation_url: str,
    author: str,
    message: str,
):
    """
    Check for duplicates and return True if duplicate exists
    """
    return (
        LinkedinConversationEntry.query.filter_by(
            conversation_url=conversation_url,
            author=author,
            message=message,
        ).first()
        is not None
    )


def create_linkedin_conversation_entry(
    conversation_url: str,
    author: str,
    first_name: str,
    last_name: str,
    date: datetime,
    profile_url: str,
    headline: str,
    img_url: str,
    connection_degree: str,
    li_url: str,
    message: str,
):
    """
    Check for duplicates and duplicate does not exist, create a new LinkedinConversationEntry
    """
    duplicate_exists = check_for_duplicate_linkedin_conversation_entry(
        conversation_url=conversation_url,
        author=author,
        message=message,
    )
    if not duplicate_exists:
        new_linkedin_conversation_entry = LinkedinConversationEntry(
            conversation_url=conversation_url,
            author=author,
            first_name=first_name,
            last_name=last_name,
            date=date,
            profile_url=profile_url,
            headline=headline,
            img_url=img_url,
            connection_degree=connection_degree,
            li_url=li_url,
            message=message,
        )
        db.session.add(new_linkedin_conversation_entry)
        db.session.commit()
        return new_linkedin_conversation_entry
    return None
