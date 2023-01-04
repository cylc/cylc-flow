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
from typing import Any, Dict

from cylc.flow.exceptions import InputError


from cylc.flow.rundb import CylcWorkflowDAO


def get_template_vars_from_db(run_dir):
    """Get template vars stored in a workflow run database.
    """
    template_vars = {}
    if (run_dir / 'log/db').exists():
        dao = CylcWorkflowDAO(str(run_dir / 'log/db'))
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


def load_template_vars(template_vars=None, template_vars_file=None):
    """Load template variables from key=value strings."""
    res = {}
    if template_vars_file:
        with open(template_vars_file, 'r') as handle:
            for line in handle:
                line = line.strip().split("#", 1)[0]
                if not line:
                    continue
                key, val = line.split("=", 1)
                res[key.strip()] = eval_var(val.strip())

    if template_vars:
        for pair in template_vars:
            key, val = pair.split("=", 1)
            res[key.strip()] = eval_var(val.strip())
    return res


def get_template_vars(options: Values) -> Dict[str, Any]:
    """Convienence wrapper for ``load_template_vars``.

    Args:
        options: Options passed to the Cylc script which is using this
            function.

    Returns:
        template_vars: Template variables to give to a Cylc config.
    """
    return load_template_vars(options.templatevars, options.templatevars_file)
