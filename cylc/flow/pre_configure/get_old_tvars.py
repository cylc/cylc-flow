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
"""Retrieve template variables stored in a workflow database.
"""

from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.templatevars import eval_var
from optparse import Values
from pathlib import Path
from typing import Union


class OldTemplateVars:
    """Gets template variables stored in workflow database.

    Mirrors the interface used in scheduler.py to get db nfo on restart.
    """
    DB = 'log/db'

    def __init__(self, run_dir):
        self.template_vars = {}
        self._get_db_template_vars(Path(run_dir))

    def _callback(self, _, row):
        """Extract key and value and run eval_var on them assigning
        them to self.template_vars.
        """
        self.template_vars[row[0]] = eval_var(row[1])

    def _get_db_template_vars(self, run_dir):
        dao = CylcWorkflowDAO(str(run_dir / self.DB))
        dao.select_workflow_template_vars(self._callback)


# Entry point:
def main(srcdir: Union[Path, str], opts: 'Values') -> dict:
    # We can calculate the source directory here!
    """Get options from a previously installed run.

    These options are stored in the database.
    Calculate the templating language used from the shebang line.

    N.B. The srcdir for this plugin to operate on is a workflow run dir.

    Args:
        srcdir: The directory of a previously run workflow.
        opts: Options Object
    """
    if not hasattr(opts, 'revalidate') or not opts.revalidate:
        return {}
    else:
        return {
            'template_variables':
                OldTemplateVars(srcdir).template_vars,
            'templating_detected':
                'template variables'
        }
