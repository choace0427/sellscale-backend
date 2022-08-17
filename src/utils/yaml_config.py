import os
import os.path
import re
from dataclasses import dataclass
from typing import Optional, Union

import yaml
import yaml.constructor
import yaml.scanner
from jinja2 import BaseLoader, Environment, Undefined


class SilentUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return ''


Json = Union[list, dict]

_IMPORTS_KEY = 'imports'
_RELATIVE_IMPORT_KEY = 'relative_import'
_ABSOLUTE_IMPORT_KEY = 'absolute_import'
_IMPORT_ALIAS_KEY = 'as'
_OVERRIDE_CONSTANTS_KEY = 'override_constants'
_CONSTANTS_KEY = 'constants'
_JINJA_INDICATOR_REGEX = r'{{[\w.]*}}'


@dataclass
class ImportRequirement:
    relative_import: str
    absolute_import: str
    import_alias: str
    override_constants: dict


def load_yaml_up_to_first_error(invalid_yaml_string: str):
    try:
        ok_yaml = yaml.safe_load(invalid_yaml_string)
        return ok_yaml
    except (yaml.constructor.ConstructorError, yaml.scanner.ScannerError) as err:
        partial_yaml = '\n'.join(
            invalid_yaml_string.split('\n')[: err.problem_mark.line]
        )
        partial_yaml = load_yaml_up_to_first_error(partial_yaml)
        return partial_yaml


def has_unresolved_jinja(yaml_string: str) -> bool:
    return bool(re.findall(_JINJA_INDICATOR_REGEX, yaml_string))


def yaml_if_ok(yaml_string) -> Optional[Json]:
    if has_unresolved_jinja(yaml_string):
        return None

    try:
        return yaml.safe_load(yaml_string)
    except Exception:
        return None


def load_yaml_from_str(
    original_yaml_string: str,
    import_file_path: str = None,
    additional_vars: dict = None,
) -> Json:
    json_obj = yaml_if_ok(original_yaml_string)
    if json_obj:
        return json_obj

    # Failed -- need to resolve custom treatment
    partial_json = load_yaml_up_to_first_error(original_yaml_string)

    jinja_context = partial_json.get(_CONSTANTS_KEY, {})
    jinja_context.update(
        dict(additional_vars or {})
    )  # Prefer additional (override) vars to constants within the file

    # Resolve Imports
    import_requirements = partial_json.get(_IMPORTS_KEY, [])

    parent_file_path = None
    if any(
        [lambda requirement: _RELATIVE_IMPORT_KEY in requirement, import_requirements]
    ):
        if not import_file_path:
            raise ValueError(
                'Can not resolve relative imports without an original file path'
            )
        parent_file_path = os.path.dirname(import_file_path)

    for import_requirement in map(import_requirement_from_dict, import_requirements):
        if not import_requirement:
            continue
        if import_requirement.relative_import:
            target = os.path.abspath(
                os.path.join(parent_file_path, import_requirement.relative_import)
            )
        else:
            target = import_requirement.absolute_import

        jinja_context[import_requirement.import_alias] = load_yaml_from_file(
            target, additional_vars=import_requirement.override_constants
        )

    # Apply Jinja Filters to raw contents
    rtemplate = Environment(loader=BaseLoader, undefined=SilentUndefined).from_string(
        original_yaml_string
    )
    jinja_processed_yaml_string = rtemplate.render(**jinja_context)

    # Reload from string with Jinja Filters resolved
    data: dict = yaml.safe_load(jinja_processed_yaml_string)

    # Remove constants & imports
    data.pop(_IMPORTS_KEY, None)
    data.pop(_CONSTANTS_KEY, None)

    return data


def import_requirement_from_dict(import_requirement: dict) -> ImportRequirement:
    req = ImportRequirement(
        relative_import=import_requirement.get(_RELATIVE_IMPORT_KEY),
        absolute_import=import_requirement.get(_ABSOLUTE_IMPORT_KEY),
        import_alias=import_requirement.get(_IMPORT_ALIAS_KEY),
        override_constants=import_requirement.get(_OVERRIDE_CONSTANTS_KEY, {}),
    )
    if req.relative_import and req.absolute_import:
        raise ValueError(
            'Can not specify two imports on the same import requirement',
            import_requirement,
        )

    if not req.import_alias:
        return None

    return req


def load_yaml_from_file(filepath: str, additional_vars: dict = None) -> Json:
    fp = open(filepath, 'r')
    raw_contents = fp.read()
    fp.close()

    return load_yaml_from_str(raw_contents, filepath, additional_vars)
