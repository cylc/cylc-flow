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

from cylc.flow.exceptions import InputError


from cylc.flow.rundb import CylcWorkflowDAO


class OldTemplateVars:
    """Gets template variables stored in workflow database.

    Mirrors the interface used in scheduler.py to get db info on restart.
    """
    DB = 'log/db'

    def __init__(self, run_dir):
        self.template_vars = {}
        self.run_dir = Path(run_dir)
        self._get_db_template_vars()

    def _callback(self, _, row):
        """Extract key and value and run eval_var on them assigning
        them to self.template_vars.
        """
        self.template_vars[row[0]] = eval_var(row[1])

    def _get_db_template_vars(self):
        if (self.run_dir / self.DB).exists():
            dao = CylcWorkflowDAO(str(self.run_dir / self.DB))
            try:
                dao.select_workflow_template_vars(self._callback)
            finally:
                dao.close()


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


def load_template_vars(
    template_vars=None, template_vars_file=None, flow_file=None
):
    """Load template variables from key=value strings."""
    res = {}
    if flow_file is not None:
        srcdir = str(Path(flow_file).parent)
        db_tvars = OldTemplateVars(srcdir).template_vars
        if db_tvars:
            for key, val in db_tvars.items():
                res[key] = val

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


def get_template_vars(options: Values, flow_file) -> Dict[str, Any]:
    """Convienence wrapper for ``load_template_vars``.

    Args:
        options: Options passed to the Cylc script which is using this
            function.
        flow_file: Path to flow_file.

    Returns:
        template_vars: Template variables to give to a Cylc config.
    """
    return load_template_vars(options.templatevars, options.templatevars_file)
