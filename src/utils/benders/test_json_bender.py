import json

from shared.base.testing import TestCase, test_main
from src.utils.benders.json_bender import JsonBender
from src.utils.config.yaml_config import load_yaml_from_file

_EXPECTED = {
    'summary_info': {
        'title': '&#128640; Strada Routing: Logistics AI | Drop #25',
        'post_date': '2021-03-16T16:00:32+00:00',
    },
    'subtitle': 'AI logistics connecting the dots + free clubhouse invites | Drop #25',
    'link': 'https://dailydropout.substack.com/p/-strada-routing-logistics-ai',
}


class JsonBenderTester(TestCase):
    def test_basic_bend(self):
        with open('substackmetrics/utils/benders/testdata/raw.json') as f:
            data = json.load(f)

        bender_config = load_yaml_from_file(
            'substackmetrics/utils/benders/testdata/bender.yml'
        )

        bender = JsonBender(bender_config)
        result = bender.bend(data)
        self.assertDictEqual(_EXPECTED, result)


if __name__ == '__main__':
    test_main()
