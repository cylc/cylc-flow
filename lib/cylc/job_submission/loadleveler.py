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

class loadleveler( job_submit ):
    """
Minimalist loadleveler job submission.
    """

    COMMAND_TEMPLATE = "llsubmit %s"

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
        # which the task job script is executed*, NOT the shell *in which it
        # is executed* (that is determined by the '#!' at the top of the
        # task job script).
        defaults[ 'shell'    ] = '/bin/ksh'

        # NOTE ON INITIALDIR directive: if the initial "running dir"
        # does not exist (or is not writable by the user?) loadleveler
        # will hold the job. However, this is not an issue for us
        # because cylc task job scripts are always submitted from $HOME.
        # add (or override with) taskdef directives

        # In case the user wants to override the above defaults:
        for d in self.directives:
            defaults[ d ] = self.directives[ d ]
        self.directives = defaults

    def construct_jobfile_submission_command( self ):
        command_template = self.job_submit_command_template
        if not command_template:
            command_template = self.COMMAND_TEMPLATE
        self.command = command_template % ( self.jobfile_path )
