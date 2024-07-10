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
"""Submits job scripts to loadleveler by the ``llsubmit`` command.

.. cylc-scope:: flow.cylc[runtime][<namespace>]

Loadleveler directives can be provided in the flow.cylc file:

.. code-block:: cylc
   :caption: global.cylc

   [platforms]
       [[myplatform]]
           job runner = loadleveler

.. code-block:: cylc
   :caption: flow.cylc

   [runtime]
       [[my_task]]
           platform = myplatform
           execution time limit = PT10M
           [[[directives]]]
               foo = bar
               baz = qux

These are written to the top of the job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   # @ foo = bar
   # @ baz = qux
   # @ wall_clock_limit = 660,600
   # @ queue

If ``restart=yes`` is specified as a directive for loadleveler, the job will
automatically trap SIGUSR1, which loadleveler may use to preempt the job. On
trapping SIGUSR1, the job will inform the workflow that it has been vacated by
loadleveler. This will put it back to the submitted state, until it starts
running again.

If :cylc:conf:`execution time limit` is specified, it is used to generate the
``wall_clock_limit`` directive. The setting is assumed to be the soft limit.
The hard limit will be set by adding an extra minute to the soft limit.  Do not
specify the ``wall_clock_limit`` directive explicitly if :cylc:conf:`execution
time limit` is specified. Otherwise, the execution time limit known by the
workflow may be out of sync with what is submitted to the job runner.

.. cylc-scope::

"""

import re

from cylc.flow.id import Tokens


class LoadlevelerHandler():

    """Loadleveler job submission"""

    DIRECTIVE_PREFIX = "# @ "
    KILL_CMD_TMPL = "llcancel '%(job_id)s'"
    POLL_CMD = "llq"
    REC_ID_FROM_SUBMIT_OUT = re.compile(
        r"""\Allsubmit:\sThe\sjob\s"(?P<id>[^"]+)"\s""")
    REC_ERR_FILTERS = [
        re.compile("^llsubmit: Processed command file through Submit Filter:")]
    SUBMIT_CMD_TMPL = "llsubmit '%(job)s'"
    VACATION_SIGNAL = "USR1"
    TIME_LIMIT_DIRECTIVE = "wall_clock_limit"

    def format_directives(self, job_conf):
        """Format the job directives for a job file."""
        job_file_path = job_conf['job_file_path']
        directives = job_conf["directives"].__class__()
        tokens = Tokens(job_conf["task_id"], relative=True)
        directives["job_name"] = (
            f'{job_conf["workflow_name"]}.{tokens["task"]}.{tokens["cycle"]}'

        )
        directives["output"] = job_file_path + ".out"
        directives["error"] = job_file_path + ".err"
        if (job_conf["execution_time_limit"] and
                directives.get(self.TIME_LIMIT_DIRECTIVE) is None):
            directives[self.TIME_LIMIT_DIRECTIVE] = "%d,%d" % (
                job_conf["execution_time_limit"] + 60,
                job_conf["execution_time_limit"])
        for key, value in list(job_conf["directives"].items()):
            directives[key] = value
        lines = []
        for key, value in directives.items():
            if value:
                lines.append("%s%s = %s" % (self.DIRECTIVE_PREFIX, key, value))
            else:
                lines.append("%s%s" % (self.DIRECTIVE_PREFIX, key))
        lines.append("%squeue" % (self.DIRECTIVE_PREFIX))
        return lines

    def filter_submit_output(self, out, err):
        """Filter the stdout/stderr output - suppress process message."""
        new_err = ""
        if err:
            for line in err.splitlines():
                if any(rec.match(line) for rec in self.REC_ERR_FILTERS):
                    continue
                new_err += line + "\n"
        return out, new_err

    @classmethod
    def filter_poll_many_output(cls, out):
        """Return a list of job IDs still in the job runner.

        Drop STEPID from the JOBID.STEPID returned by 'llq'.
        """
        job_ids = []
        for line in out.splitlines():
            try:
                head = line.split(None, 1)[0]
            except IndexError:
                continue
            job_ids.append(".".join(head.split(".")[:2]))
        return job_ids

    def get_vacation_signal(self, job_conf):
        """Return "USR1" if "restart" directive is "yes"."""
        if job_conf["directives"].get("restart") == "yes":
            return self.VACATION_SIGNAL


JOB_RUNNER_HANDLER = LoadlevelerHandler()
