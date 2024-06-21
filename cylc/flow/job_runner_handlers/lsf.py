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
"""Submits job scripts to IBM Platform LSF by the ``bsub`` command.

.. cylc-scope:: flow.cylc[runtime][<namespace>]

LSF directives can be provided in the flow.cylc file:

.. code-block:: cylc
   :caption: global.cylc

   [platforms]
       [[myplatform]]
           job runner = lsf

.. code-block:: cylc
   :caption: flow.cylc

   [runtime]
       [[my_task]]
           platform = myplatform
           execution time limit = PT10M
           [[[directives]]]
               -q = foo

These are written to the top of the job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   #BSUB -q = foo
   #BSUB -W = 10

If :cylc:conf:`execution time limit` is specified, it is used to generate the
``-W`` directive. Do not specify the ``-W`` directive
explicitly if :cylc:conf:`execution time limit` is specified. Otherwise, the
execution time limit known by the workflow may be out of sync with what is
submitted to the job runner.

.. cylc-scope::

"""

import math
import re

from cylc.flow.id import Tokens


class LSFHandler():
    """IBM Platform LSF bsub job submission"""

    DIRECTIVE_PREFIX = "#BSUB "
    FAIL_SIGNALS = ("EXIT", "ERR", "XCPU", "TERM", "INT", "SIGUSR2")
    KILL_CMD_TMPL = "bkill '%(job_id)s'"
    POLL_CMD = "bjobs"
    REC_ID_FROM_SUBMIT_OUT = re.compile(r"^Job <(?P<id>\d+)>")
    SUBMIT_CMD_TMPL = "bsub"
    TIME_LIMIT_DIRECTIVE = "-W"

    @classmethod
    def format_directives(cls, job_conf):
        """Format the job directives for a job file."""
        job_file_path = job_conf['job_file_path']
        directives = job_conf["directives"].__class__()
        tokens = Tokens(job_conf['task_id'], relative=True)
        directives["-J"] = (
            f'{tokens["task"]}.{tokens["cycle"]}.{job_conf["workflow_name"]}'
        )
        directives["-o"] = job_file_path + ".out"
        directives["-e"] = job_file_path + ".err"
        if (
            job_conf["execution_time_limit"]
            and directives.get(cls.TIME_LIMIT_DIRECTIVE) is None
        ):
            directives[cls.TIME_LIMIT_DIRECTIVE] = str(math.ceil(
                job_conf["execution_time_limit"] / 60))
        for key, value in list(job_conf["directives"].items()):
            directives[key] = value
        lines = []
        for key, value in directives.items():
            if value:
                lines.append("%s%s %s" % (cls.DIRECTIVE_PREFIX, key, value))
            else:
                lines.append("%s%s" % (cls.DIRECTIVE_PREFIX, key))
        return lines

    @classmethod
    def get_submit_stdin(cls, job_file_path, _):
        """Return proc_stdin_arg, proc_stdin_value."""
        return (open(job_file_path), None)  # noqa: SIM115 (open fh by design)


JOB_RUNNER_HANDLER = LSFHandler()
