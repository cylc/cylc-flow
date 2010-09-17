#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os, re
import tempfile
from job_submit import job_submit

class background( job_submit ):
    # This class overrides job submission command construction so that
    # the cylc task execution file will run in a background shell.

    def construct_command( self ):
        # Redirection of stdin here allows "background execution" of the
        # task even on a remote host (if one is specified in the taskdef
        # file) - ssh can exit immediately after invoking the job
        # script, without waiting for the remote process to finish.

        if self.local_job_submit:
            # can uniquify the name locally
            out = tempfile.mktemp( 
                prefix = self.task_id + "-",
                suffix = ".out", 
                dir = os.path.join( self.homedir, self.__class__.joblog_dir ))

            err = re.sub( '\.out$', '.err', out )

            # record log files for access by cylc view
            self.logfiles.replace_path( '/.*/' + self.task_id + '-.*\.out', out )
            self.logfiles.replace_path( '/.*/' + self.task_id + '-.*\.err', err )

        else:
            # remote jobs are submitted from remote $HOME, via ssh
            out = self.task_id + '.out'
            err = self.task_id + '.err'

        self.command = self.jobfile_path + " </dev/null 1> " + out + " 2> " + err + " &" 
