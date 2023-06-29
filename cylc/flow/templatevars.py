# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Load custom variables for template processor."""

from ast import literal_eval
from optparse import Values
from typing import Any, Dict, List, Optional, Set, Union

from cylc.flow import LOG
from cylc.flow.exceptions import InputError
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
from cylc.flow.workflow_files import WorkflowFiles

from pathlib import Path


OVERWRITE_WARNING = (
    'Template variable {} redefined:'
    ' the previous value will be overwritten.'
)


def get_template_vars_from_db(run_dir: 'Path') -> dict:
    """Get template vars stored in a workflow run database.
    """
    pub_db_file = (
        run_dir / WorkflowFiles.LogDir.DIRNAME / WorkflowFiles.LogDir.DB
    )
    template_vars: dict = {}
    if not pub_db_file.exists():
        return template_vars
    WorkflowDatabaseManager.check_db_compatibility(pub_db_file)
    with CylcWorkflowDAO(pub_db_file, is_public=True) as dao:
        dao.select_workflow_template_vars(
            lambda _, row: template_vars.__setitem__(row[0], eval_var(row[1]))
        )
    return template_vars


def eval_var(var):
    """Wrap ast.literal_eval to provide more helpful error.

    Examples:
        >>> eval_var('42')
        42
        >>> eval_var('"string"')
        'string'
        >>> eval_var('string')
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: Invalid template variable: string
        (note string values must be quoted)
        >>> eval_var('[')
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: Invalid template variable: [
        (values must be valid Python literals)

    """
    try:
        return literal_eval(var)
    except ValueError:
        raise InputError(
            f'Invalid template variable: {var}'
            '\n(note string values must be quoted)'
        ) from None
    except SyntaxError:
        raise InputError(
            f'Invalid template variable: {var}'
            '\n(values must be valid Python literals)'
        ) from None


def parse_string_list(stringlist: str) -> List:
    """Parse a comma separated string list into a Python string list.

    Examples:
        >>> parse_string_list('a,b,c')
        ['a', 'b', 'c']
        >>> parse_string_list('a,"b,b",c')
        ['a', 'b,b', 'c']
        >>> parse_string_list("a,'b,b','c'")
        ['a', 'b,b', 'c']
    """
    list_ = []
    in_quotes = False
    buffer = ''
    for char in stringlist:
        if char in {'"', "'"}:
            in_quotes = not in_quotes
        elif not in_quotes and char == ',':
            list_.append(buffer)
            buffer = ''
        else:
            buffer += char
    list_.append(buffer)
    return list_


def load_template_vars(
    template_vars: Optional[List[str]] = None,
    template_vars_file: Union[Path, str, None] = None,
    templatevars_lists: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Load template variables from key=value strings."""
    keys: Set[str] = set()
    invalid_vars: str = ''

    # Parse Template vars set by file (-S)
    file_tvars: Dict[str, Any] = {}
    if template_vars_file:
        with open(template_vars_file, 'r') as handle:
            for line in handle:
                line = line.strip().split("#", 1)[0]
                if not line:
                    continue
                try:
                    key, val = line.split("=", 1)
                except ValueError:
                    invalid_vars += f'\n * {line}'
                    continue
                file_tvars[key.strip()] = eval_var(val.strip())
                keys.add(key.strip())

    cli_tvars: Dict[str, Any] = {}
    tvars_lists: Dict[str, str] = {}
    for input_, result, func in (
        (template_vars, cli_tvars, eval_var),
        (templatevars_lists, tvars_lists, parse_string_list)
    ):
        for pair in input_ or []:
            # Handle ValueError
            try:
                key, val = pair.split("=", 1)
            except ValueError:
                invalid_vars += f'\n * {pair}'
                continue
            key, val = key.strip(), val.strip()
            if key in result:
                LOG.warning(OVERWRITE_WARNING.format(key))
            result[key] = func(val)
            keys.add(key)

    # Raise an error if there are any args without the form key=value.:
    if invalid_vars:
        raise InputError(
            'Template variables must be set with key=value(s):'
            + invalid_vars
        )

    # Explicitly record which source of tvars over-rides which.
    res = {}
    badkeys = ''
    for key in keys:
        if key in cli_tvars and key in tvars_lists:
            badkeys += (
                f"\n * {key}={cli_tvars[key]} and {key}={tvars_lists[key]}")
        else:
            res[key] = cli_tvars.get(
                key, tvars_lists.get(
                    key, file_tvars.get(key)))

    # Raise an error if there are any key-clashes between tvars and tvars_list
    if badkeys:
        raise InputError(
            "You can't set the same template variable with both -s and -z:"
            + badkeys
        )

    return res


def get_template_vars(options: Values) -> Dict[str, Any]:
    """Convienence wrapper for ``load_template_vars``.

    Args:
        options: Options passed to the Cylc script which is using this
            function.

    Returns:
        template_vars: Template variables to give to a Cylc config.
    """
    return load_template_vars(
        options.templatevars,
        options.templatevars_file,
        options.templatevars_lists
    )
