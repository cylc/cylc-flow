#!/usr/bin/env python

import os, re
import tempfile
from job_submit import job_submit

class loadleveler( job_submit ):
    """
Minimalist loadleveler job submission.
    """
    def set_directives( self ):
        self.directive_prefix = "# @ "
        self.final_directive  = "# @ queue"

        defaults = {}
        defaults[ 'job_name' ] = self.task_id
        defaults[ 'output'   ] = self.stdout_file
        defaults[ 'error'    ] = self.stderr_file

        # NOTE ON SHELL DIRECTIVE: on AIX, '#@ shell = /bin/bash'
        # results in the job executing in a non-login shell (.profile
        # not sourced) whereas /bin/ksh does get a login shell. WTF?! In
        # any case this directive appears to affect only the shell *from
        # which the job script is executed*, NOT the shell *in which it
        # is executed* (that is determined by the '#!' at the top of the
        # job script).
        defaults[ 'shell'    ] = '/bin/ksh'

        # NOTE ON INITIALDIR directive: if the initial "running dir"
        # does not exist (or is not writable by the user?) loadleveler
        # will hold the job. However, this is not an issue for us
        # because cylc job scripts are always submitted from $HOME.
        # add (or override with) taskdef directives

        # Now, in case the user has overridden the above defaults:
        for d in self.directives:
            defaults[ d ] = self.directives[ d ]
        self.directives = defaults

    def construct_jobfile_submission_command( self ):
        self.command = 'llsubmit ' + self.jobfile_path
