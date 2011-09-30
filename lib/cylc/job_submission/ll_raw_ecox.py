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

from ll_raw import ll_raw
from _ecox import ecox

class ll_raw_ecox( ecox, ll_raw ):
    def __init__( self, task_id, pre_command, task_command,
            post_command, task_env, ns_hier, directives, manual_messaging,
            logfiles, log_dir, share_dir, work_dir, task_owner, remote_host, remote_cylc_dir,
            remote_suite_dir, remote_shell_template, remote_log_dir,
            job_submit_command_template, job_submission_shell ): 

        self.check( task_id, task_owner, directives )

        loadleveler.__init__( self, task_id, pre_command, task_command,
            post_command, task_env, ns_hier, directives, manual_messaging,
            logfiles, log_dir, share_dir, work_dir, task_owner, remote_host, remote_cylc_dir,
            remote_suite_dir, remote_shell_template, remote_log_dir,
            job_submit_command_template, job_submission_shell )
