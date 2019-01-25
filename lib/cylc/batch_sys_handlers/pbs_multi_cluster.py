#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""PBS batch system job submission and manipulation: multi-cluster variant.

Support PBS clients that front heterogeneous clusters where the Job ID returned
by qsub is <id>.<server>. PBS 13 qstat and qdel need <id>.<server>@<server>.
From PBS 14, the standard cylc PBS module works ("@<server>" is not needed).

So this PBS handler writes "job_id@server" to the job status file, and appends
"@server" to Job IDs returned by qstat, to matched the stored IDs.
"""

import re
from cylc.batch_sys_handlers.pbs import PBSHandler


# Match and extract PBS Job ID of the form "<job>.<host>"
REC_JOB = re.compile(r'^ *(?P<job>[^ ]+?)\.(?P<host>[^ ]+) *$')
# Replace with "<job>.<host>@<host>"
REP_JOB = r'\g<job>.\g<host>@\g<host>'


class PBSMulticlusterHandler(PBSHandler):

    @classmethod
    def filter_poll_many_output(cls, out):
        """Extract and return Job IDs from qstat output.

        Ignore first two lines of qstat output (header lines).
        Manipulate Job IDs as described above, if matched, else leave as-is.
        """
        job_ids = []
        for line in out.splitlines()[2:]:
            job_ids.append(cls.manip_job_id(line))
        return job_ids

    @classmethod
    def manip_job_id(cls, job_id):
        """For job_id of the form "id.server", return job_id@server."""
        return re.sub(REC_JOB, REP_JOB, job_id.strip())


BATCH_SYS_HANDLER = PBSMulticlusterHandler()
