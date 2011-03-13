#!/usr/bin/env python

import os, re
import tempfile
from job_submit import job_submit

class ll_basic( job_submit ):
    # Submit a job to run via loadleveler (llsubmit)

    def __init__( self, task_id, ext_task, task_env, dirs, extra, logs, owner, host ): 
        # parent class init first
        job_submit.__init__( self, task_id, ext_task, task_env, dirs, extra, logs, owner, host ) 

        if self.local_job_submit:
            # can uniquify the name locally
            out = tempfile.mktemp(
                prefix = task_id + '-', 
                suffix = ".out",
                dir= self.joblog_dir ) 

            err = re.sub( '\.out$', '.err', out )

            # record log files for access by cylc view
            self.logfiles.replace_path( '/.*/' + task_id + '-.*\.out', out )
            self.logfiles.replace_path( '/.*/' + task_id + '-.*\.err', err )

        else:
            # remote jobs are submitted from remote $HOME, via ssh
            out = self.task_id + '.out'
            err = self.task_id + '.err'


        # if task is owned, replace suite owner with task owner in out
        # and err file paths. TO DO: this will not have the desired
        # effect if the suite and task owners' home directories are not
        # of the same structure. TO DO: consider ssh'd remote tasks too.
        out = re.sub( self.suite_owner, self.owner, out )
        err = re.sub( self.suite_owner, self.owner, err )

        # default directives
        directives = {}
        directives[ 'shell'    ] = '/bin/bash'
        #directives[ 'class'    ] = 'serial'
        directives[ 'class'    ] = 'test_linux'
        directives[ 'job_name' ] = task_id
        directives[ 'output'   ] = out
        directives[ 'error'    ] = err

        if self.local_job_submit:
            # This is probably  not necessary as we cd to homedir before
            # submitting. 
            directives[ 'initialdir' ] = self.homedir
            # For remote job submits we don't necessarily know the
            # remote homedir, but ssh automatically puts us there, so
            # don't need the directive.

        # add (or override with) taskdef directives
        for d in self.directives:
            directives[ d ] = self.directives[ d ]

        # now replace
        self.directives = directives

        self.directive_prefix = "# @ "
        self.final_directive  = "# @ queue"

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfile_path
