from app import db
from tests.test_utils.decorators import use_app_context
from src.li_conversation.models import LinkedInConvoMessage
from src.prospecting.models import ProspectStatus
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_bump_framework,
    basic_linkedin_conversation_entry
)
from src.li_conversation.services import (
    generate_chat_gpt_response_to_conversation_thread_helper,
    update_linkedin_conversation_entries,
    create_linkedin_conversation_entry,
    update_li_conversation_extractor_phantom,
    get_li_conversation_entries,
)
from datetime import datetime
from app import app
import mock


class SampleStatusCode:
    def __init__(self, status_code):
        self.status_code = status_code


class PhantomBusterAgentMock:
    def __init__(self, *args, **kwargs):
        pass

    def get_output():
        return [{"conversationalUrl": "..."}]

    def run_phantom():
        return SampleStatusCode(200)

    def update_argument(*args, **kwargs):
        pass


@use_app_context
@mock.patch(
    "src.li_conversation.services.PhantomBusterAgent",
    return_value=PhantomBusterAgentMock,
)
def test_update_linkedin_conversation_entries(pb_agent_mock):
    """Test update_linkedin_conversation_entries"""
    update_linkedin_conversation_entries()


@use_app_context
def test_create_linkedin_conversation_entry():
    """Test create_linkedin_conversation_entry"""
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr.auth_token = "123123"
    conversation_url = "https://www.linkedin.com/messaging/conversations/123456789"
    author = "John Doe"
    first_name = "John"
    last_name = "Doe"
    date = datetime.now()
    profile_url = "https://www.linkedin.com/in/johndoe"
    headline = "Software Engineer"
    img_url = "https://media-exp1.licdn.com/dms/image/C4D03AQGz0QZ1QwZ8Rg/profile-displayphoto-shrink_800_800/0/1605817042181?e=1623283200&v=beta&t=3k0cVbH6oYJ7Rv1XQzU6Zx1Q2zW8ZJj6Z5p5H5J5y5g"
    connection_degree = "2nd"
    li_url = "https://www.linkedin.com/in/johndoe"
    message = "Hello, how are you?"
    create_linkedin_conversation_entry(
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
        client_sdr_id=client_sdr.id
    )


@use_app_context
@mock.patch(
    "src.li_conversation.services.PhantomBusterAgent",
    return_value=PhantomBusterAgentMock,
)
def test_update_li_conversation_extractor_phantom(
    update_li_conversation_extractor_phantom_mock,
):
    """Test update_li_conversation_extractor_phantom"""
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr.li_at_token = "123123"
    client_sdr.last_li_at_token = "123123"
    db.session.add(client_sdr)
    db.session.commit()
    client_sdr_id = client_sdr.id
    update_li_conversation_extractor_phantom(client_sdr_id)


@use_app_context
def test_get_li_conversation_entries():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr, li_conversation_thread_id='test-thread-id')
    li_entry = basic_linkedin_conversation_entry(\
        conversation_url="test-thread-id",
        author="test-author",
        message="test-message",
        connection_degree="test-degree",
        date=datetime.now(),
    )

    client.active = True
    prospect.status = ProspectStatus.ACTIVE_CONVO

    data = get_li_conversation_entries()
    assert data[0]['conversation_url'] == 'test-thread-id'
    assert data[0]['author'] == 'test-author'
    assert data[0]['message'] == 'test-message'
    assert data[0]['connection_degree'] == 'test-degree'
    assert data[0]['sdr_name'] == 'Test SDR'


@use_app_context
@mock.patch("src.li_conversation.services.wrapped_chat_gpt_completion", return_value="This is a test response")
def test_generate_chat_gpt_response_to_conversation_thread_helper(mock_chat_gpt_completion):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr, li_conversation_thread_id='test-thread-id')

    m: LinkedInConvoMessage = LinkedInConvoMessage(
        author="test-author",
        message="test-message",
        connection_degree="You",
    )

    bump_framework = basic_bump_framework(client_sdr, archetype, use_account_research=True)
    response, _ = generate_chat_gpt_response_to_conversation_thread_helper(
        prospect.id,
        [m],
        bump_framework.id,
        account_research_copy="test-account-research-copy",
    )
    mocked_arguments = mock_chat_gpt_completion.call_args[0]
    assert 'Naturally integrate pieces' in mocked_arguments[0][0].get('content')
    assert response == "This is a test response"

    bump_framework_no_research = basic_bump_framework(client_sdr, archetype, use_account_research=False)
    response, _ = generate_chat_gpt_response_to_conversation_thread_helper(
        prospect.id,
        [m],
        bump_framework_no_research.id,
        account_research_copy="test-account-research-copy",
    )
    mocked_arguments = mock_chat_gpt_completion.call_args[0]
    assert 'Naturally integrate pieces' not in mocked_arguments[0][0].get('content')
    assert response == "This is a test response"
