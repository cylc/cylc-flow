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
"""Submits job scripts to PBS (or Torque) by the ``qsub`` command.

.. cylc-scope:: flow.cylc[runtime][<namespace>]

PBS directives can be provided in the flow.cylc file:

.. code-block:: cylc
   :caption: global.cylc

   [platforms]
       [[myplatform]]
           job runner = pbs

.. code-block:: cylc
   :caption: flow.cylc

   [runtime]
       [[my_task]]
           platform = myplatform
           execution time limit = PT1M
           [[[directives]]]
               -V =
               -q = foo
               -l nodes = 1

These are written to the top of the job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   #PBS -V
   #PBS -q foo
   #PBS -l nodes=1
   #PBS -l walltime=60

If :cylc:conf:`execution time limit` is specified, it is used to generate the
``-l walltime`` directive. Do not specify the ``-l walltime`` directive
explicitly if :cylc:conf:`execution time limit` is specified.  Otherwise, the
execution time limit known by the workflow may be out of sync with what is
submitted to the job runner.

.. cylc-scope::

"""

import re

from cylc.flow.id import Tokens


class PBSHandler:

    """PBS job submission and manipulation."""

    DIRECTIVE_PREFIX = "#PBS "
    # PBS fails a job submit if job "name" in "-N name" is too long.
    # For version 12 or below, this is 15 characters.
    # You can modify this in the site/user `global.cylc` like this
    # [platforms]
    #     [[the-name-of-my-pbs-platform]]
    #         job runner = pbs
    #         job name length maximum = 15
    JOB_NAME_LEN_MAX = 236
    KILL_CMD_TMPL = "qdel '%(job_id)s'"
    # N.B. The "qstat JOB_ID" command returns 1 if JOB_ID is no longer in the
    # system, so there is no need to filter its output.
    POLL_CMD = "qstat"
    POLL_CANT_CONNECT_ERR = "cannot connect to server"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"^\s*(?P<id>\d+)", re.M)
    SUBMIT_CMD_TMPL = "qsub '%(job)s'"
    TIME_LIMIT_DIRECTIVE = "-l walltime"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = job_conf['job_file_path']
        directives = job_conf["directives"].__class__()  # an ordereddict
        # Change task/runM to task-runM in the job name
        # (PBS 19.2.1+ does not allow '/' in job names)
        tokens = Tokens(job_conf['task_id'], relative=True)
        directives["-N"] = (
            f'{tokens["task"]}.{tokens["cycle"]}'
            f".{job_conf['workflow_name'].replace('/', '-')}"
        )
        job_name_len_max = job_conf['platform'].get(
            "job name length maximum",
            self.JOB_NAME_LEN_MAX
        )
        if job_name_len_max:
            directives["-N"] = directives["-N"][0:job_name_len_max]

        directives["-o"] = job_file_path + ".out"
        directives["-e"] = job_file_path + ".err"
        if (
            job_conf["execution_time_limit"]
            and directives.get(self.TIME_LIMIT_DIRECTIVE) is None
        ):
            directives[self.TIME_LIMIT_DIRECTIVE] = "%d" % job_conf[
                "execution_time_limit"]
        for key, value in list(job_conf["directives"].items()):
            directives[key] = value
        lines = []
        for key, value in directives.items():
            if value and " " in key:
                # E.g. -l walltime=3:00:00
                lines.append("%s%s=%s" % (self.DIRECTIVE_PREFIX, key, value))
            elif value:
                # E.g. -q queue_name
                lines.append("%s%s %s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                # E.g. -V
                lines.append(self.DIRECTIVE_PREFIX + key)
        return lines

    @classmethod
    def filter_poll_many_output(cls, out):
        """Strip trailing stuff from the job ID."""
        return cls.REC_ID_FROM_SUBMIT_OUT.findall(out)


JOB_RUNNER_HANDLER = PBSHandler()
