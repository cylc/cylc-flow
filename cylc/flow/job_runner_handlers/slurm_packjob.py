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
"""SLURM job submission and manipulation.

Includes directive prefix workaround for heterogeneous job support, for older
Slurm versions that use "packjob" instead of "hetjob".

"""

import re
from cylc.flow.job_runner_handlers.slurm import SLURMHandler


class SLURMPackjobHandler(SLURMHandler):
    """SLURM job submission and manipulation."""

    # Heterogeneous job support
    #  Match artificial directive prefix
    REC_HETJOB = re.compile(r"^packjob_(\d+)_")
    #  Separator between heterogeneous job directive sections
    SEP_HETJOB = "#SBATCH packjob"


JOB_RUNNER_HANDLER = SLURMPackjobHandler()
