#!/usr/bin/env python

import os, re
import tempfile
from job_submit import job_submit

class at_now( job_submit ):
    # This class overrides job submission command construction so that
    # the cylc task execution file will be submitted to the Unix 'at'
    # scheduler, with output redirected to file instead of to mail.

    def construct_command( self ):

        if self.local_job_submit:
            # can uniquify the name locally
            out = tempfile.mktemp( 
                suffix = ".out", 
                prefix = self.task_id + "-",
                dir = self.joblog_dir )

            err = re.sub( '\.out$', '.err', out )

            # record log files for access by cylc view
            self.logfiles.replace_path( '/.*/' + self.task_id + '-.*\.out', out )
            self.logfiles.replace_path( '/.*/' + self.task_id + '-.*\.err', err )

        else:
            # remote jobs are submitted from remote $HOME, via ssh
            out = self.task_id + '.out'
            err = self.task_id + '.err'

        self.command = 'at now <<eof\n' + self.jobfile_path + ' 1> ' + out + ' 2> ' + err + '\neof'
