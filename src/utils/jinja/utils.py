from jinja2 import BaseLoader, Environment


def render_jinja(template: str, context: dict):
    template = Environment(loader=BaseLoader).from_string(template)
    return template.render(**context)
