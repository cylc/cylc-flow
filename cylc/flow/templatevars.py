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
from pathlib import Path
from typing import Any, Dict

from cylc.flow import iter_entry_points
from cylc.flow.exceptions import UserInputError, PluginError
from cylc.flow.parsec.fileparse import merge_template_vars
from cylc.flow.pathutil import get_cylc_run_dir, is_relative_to
from cylc.flow.workflow_files import is_installed


def eval_var(var):
    """Wrap ast.literal_eval to provide more helpful error.

    Examples:
        >>> eval_var('42')
        42
        >>> eval_var('"string"')
        'string'
        >>> eval_var('string')
        Traceback (most recent call last):
        cylc.flow.exceptions.UserInputError: Invalid template variable: string
        (note string values must be quoted)
        >>> eval_var('[')
        Traceback (most recent call last):
        cylc.flow.exceptions.UserInputError: Invalid template variable: [
        (values must be valid Python literals)

    """
    try:
        return literal_eval(var)
    except ValueError:
        raise UserInputError(
            f'Invalid template variable: {var}'
            '\n(note string values must be quoted)'
        ) from None
    except SyntaxError:
        raise UserInputError(
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


def get_template_vars(options: Values, flow_file: Path) -> Dict[str, Any]:
    """Get Template Vars from either an uninstalled or installed flow.

    Designed to allow a Cylc script to be run on an installed workflow where
    template variables have been processed and saved to file, but fallback to
    evaluating templating if run on an uninstalled workflow.

    Args:
        options: Options passed to the Cylc script which is using this
            function.
        flow_file: Path to the ``flow.cylc`` (or ``suite.rc``) file defining
            this workflow.

    Returns:
        template_vars: Template variables to give to a Cylc config.
    """
    template_vars = load_template_vars(
        options.templatevars, options.templatevars_file
    )
    if (
        is_relative_to(flow_file, get_cylc_run_dir()) and
        is_installed(flow_file.parent)
    ):
        return template_vars
    # Else we act as if we might be looking at a cylc-src dir.
    source = Path(flow_file).parent
    for entry_point in iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            ep_result = entry_point.resolve()(
                srcdir=source, opts=options
            )
            template_vars = merge_template_vars(
                template_vars, ep_result)
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None
    return template_vars
