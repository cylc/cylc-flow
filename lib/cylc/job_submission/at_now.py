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
    COMMAND_TEMPLATE = "echo \"%(jobfile_path)s 1>%(stdout_file)s 2>%(stderr_file)s\" | at now"
    def construct_jobfile_submission_command( self ):
        self.command = self.COMMAND_TEMPLATE % { "jobfile_path": self.jobfile_path,
                                                 "stdout_file": self.stdout_file,
                                                 "stderr_file": self.stderr_file }
