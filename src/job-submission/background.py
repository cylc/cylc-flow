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

import os, re
import tempfile
from job_submit import job_submit

class background( job_submit ):
    """
Run the task job script directly in a background shell. Owned tasks cannot
easily be run via sudo for this method, as /etc/sudoers would have to 
be configured to allow the suite owner to execute 
'sudo -u TASK-OWNER JOBFILE' for any conceivable jobfile.
    """
    def construct_jobfile_submission_command( self ):
        # stdin redirection (< /dev/null) allows background execution 
        # even on a remote host - ssh can exit without waiting for the
        # remote process to finish.
        self.command = self.jobfile_path + " </dev/null" + \
                " 1> " + self.stdout_file + " 2> " + self.stderr_file + " &"
