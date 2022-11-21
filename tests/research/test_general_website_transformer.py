from tests.decorators import use_app_context
from test_utils import test_app
from src.research.website.general_website_transformer import (
    find_points_from_website,
    generate_general_website_research_points,
)
import mock


def test_find_points_from_website():
    url = ""
    points = find_points_from_website(url)

    assert points == None


def test_find_points_from_website():
    url = "https://vessel.land/"
    points = find_points_from_website(url)

    assert len(points[0]) > 0


@mock.patch(
    "src.research.website.general_website_transformer.get_basic_openai_completion",
    return_value=["this is an openai completion mock"],
)
def test_generate_general_website_research_points(open_ai_completion_patch):
    url = "https://vessel.land/"
    data = generate_general_website_research_points(url)
    assert data.get("raw_data") == {"url": url}
    assert len(data.get("prompt")) > 10
    assert data.get("response") == "this is an openai completion mock"
    assert open_ai_completion_patch.call_count == 1
