#!/usr/bin/env python

import os, re
import tempfile
from job_submit import job_submit

class background( job_submit ):
    """
Run the task execution script directly in a background shell. Owned tasks cannot
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
