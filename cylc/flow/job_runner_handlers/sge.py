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
"""Submits job scripts to Sun/Oracle Grid Engine with ``qsub``.

.. cylc-scope:: flow.cylc[runtime][<namespace>]

SGE directives can be provided in the flow.cylc file:

.. code-block:: cylc
   :caption: global.cylc

   [platforms]
       [[sge_platform]]
           job runner = sge

.. code-block:: cylc
   :caption: flow.cylc

   [runtime]
       [[my_task]]
           platform = sge_platform
           execution time limit = P1D
           [[[directives]]]
               -cwd =
               -q = foo
               -l h_data = 1024M
               -l h_rt = 24:00:00

These are written to the top of the job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   #$ -cwd
   #$ -q foo
   #$ -l h_data=1024M
   #$ -l h_rt=24:00:00

If :cylc:conf:`execution time limit` is specified, it is used to generate the
``-l h_rt`` directive. Do not specify the ``-l h_rt`` directive explicitly if
:cylc:conf:`execution time limit` is specified.  Otherwise, the execution time
limit known by the workflow may be out of sync with what is submitted to the
job runner.

.. cylc-scope::

"""

import re

from cylc.flow.id import Tokens


class SGEHandler:

    """SGE qsub job submission"""

    DIRECTIVE_PREFIX = "#$ "
    KILL_CMD_TMPL = "qdel '%(job_id)s'"
    # N.B. The "qstat -j JOB_ID" command returns 1 if JOB_ID is no longer in
    # the system, so there is no need to filter its output.
    POLL_CMD = "qstat"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"\D+(?P<id>\d+)\D+")
    SUBMIT_CMD_TMPL = "qsub '%(job)s'"
    TIME_LIMIT_DIRECTIVE = "-l h_rt"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = job_conf['job_file_path']
        directives = job_conf['directives'].__class__()
        tokens = Tokens(job_conf['task_id'], relative=True)
        directives['-N'] = (
            f'{job_conf["workflow_name"]}.{tokens["task"]}.{tokens["cycle"]}'
        )
        directives['-o'] = job_file_path + ".out"
        directives['-e'] = job_file_path + ".err"
        if (job_conf["execution_time_limit"] and
                directives.get(self.TIME_LIMIT_DIRECTIVE) is None):
            directives[self.TIME_LIMIT_DIRECTIVE] = "%d:%02d:%02d" % (
                job_conf["execution_time_limit"] / 3600,
                (job_conf["execution_time_limit"] / 60) % 60,
                job_conf["execution_time_limit"] % 60)
        for key, value in list(job_conf['directives'].items()):
            directives[key] = value
        lines = []
        for key, value in directives.items():
            if value and " " in key:
                # E.g. -l h_rt=3:00:00
                lines.append("%s%s=%s" % (self.DIRECTIVE_PREFIX, key, value))
            elif value:
                # E.g. -q queue_name
                lines.append("%s%s %s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                # E.g. -V
                lines.append("%s%s" % (self.DIRECTIVE_PREFIX, key))
        return lines

    @classmethod
    def get_poll_many_cmd(cls, _):
        """Return poll command"""
        # No way to run POLL_CMD on specific job id(s). List all user's jobs.
        # job_runner_mgr._jobs_poll_runner checks requested id in list.
        return [cls.POLL_CMD]


JOB_RUNNER_HANDLER = SGEHandler()
