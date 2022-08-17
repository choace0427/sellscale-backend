from sellscale.utils.jinja.utils import render_jinja


def render_file(template_file_path: str, target_file_path: str, context: dict):
    rendered_file_contents = render_jinja(open(template_file_path).read(), context)
    with open(target_file_path, 'w+') as task_config_file:
        task_config_file.write(rendered_file_contents)
