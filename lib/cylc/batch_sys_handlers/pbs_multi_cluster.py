#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
"""PBS batch system job submission and manipulation.

This variant supports heteorogenous clusters where the Job ID returned by qsub
is <job-id>.<server>. Prior to PBS 14 job query and kill need to target
<job-id>@<server>.

This is achieved by:
  - providing a manip_job_id() method to append "@<server>" to the Job ID
    returned by qsub, for writing to the job status file.
  - providing a filter_poll_many_output() method to append "@<server>" to the
    Job IDs returned by qstat, for comparison with those known by cylc.

From PBS 14 the standard "pbs" module works ("@<server>" is not needed).
"""

from cylc.batch_sys_handlers.pbs import PBSHandler


class PBSMulticlusterHandler(PBSHandler):

    @classmethod
    def filter_poll_many_output(cls, out):
        out = out.strip()
        job_ids = []
        lines = out.split('\n')
        for line in lines[2:]:
            job = line.split()[0]
            _, server = job.split('.')
            job_ids.append(job + '@' + server)
        return job_ids

    @classmethod
    def manip_job_id(cls, job_id):
        """Manipulate the job ID returned by qsub."""
        _, server = job_id.split('.')
        return job_id + '@' + server


BATCH_SYS_HANDLER = PBSMulticlusterHandler()
