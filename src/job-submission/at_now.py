#!/usr/bin/env python

import os, re
import tempfile
from job_submit import job_submit

class at_now( job_submit ):
    """
Submit the job script to the simple 'at' scheduler. The 'atd' daemon
service must be running. For owned tasks run via sudo, /etc/sudoers must
be configured to allow the suite owner to execute 'sudo -u TASK-OWNER at'.
    """
    def construct_jobfile_submission_command( self ):
        self.command = 'at now <<EOF\n' + self.jobfile_path + \
                ' 1> ' + self.stdout_file + ' 2> ' + self.stderr_file + '\nEOF'
