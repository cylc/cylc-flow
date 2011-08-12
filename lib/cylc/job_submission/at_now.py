#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

from job_submit import job_submit

class at_now( job_submit ):
    """
Submit the task job script to the simple 'at' scheduler. The 'atd' daemon
service must be running. For owned tasks run via sudo, /etc/sudoers must
be configured to allow the suite owner to execute 'sudo -u TASK-OWNER at'.
    """
    Q_CMD = "at now"
    TEMPLATE_L = "echo \"%(cmd)s 1>%(out)s 2>%(err)\" | %(q_cmd)"
    TEMPLATE_R = ( "mkdir -p $(dirname %(cmd)s)"
                   + " && cat >%(cmd)s"
                   + " && chmod +x %(cmd)s"
                   + " && (" + TEMPLATE_L + ")" )
    def construct_jobfile_submission_command( self ):
        template = TEMPLATE_L
        data = { "cmd": self.jobfile_path,
                 "out": self.stdout_file,
                 "err": self.stderr_file
                 "q_cmd": Q_CMD}
        if not self.local_job_submit:
            template = TEMPLATE_R
            data["cmd"] = self.remote_jobfile_path
        self.command = template % data
