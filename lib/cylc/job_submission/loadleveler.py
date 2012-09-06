#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

import re
from job_submit import job_submit

class loadleveler( job_submit ):
    """
Loadleveler job submission.
    """

    COMMAND_TEMPLATE = "llsubmit %s"

    def set_directives( self ):
        self.jobconfig['directive prefix'] = "# @"
        self.jobconfig['directive connector'] = " = "
        self.jobconfig['directive final'] = "# @ queue"

        defaults = {}
        defaults[ 'job_name' ] = self.task_id
        # Replace literal '$HOME' in stdout and stderr file paths with '' 
        # because environment variables are not interpreted in directives.
        # (For remote tasks the local home directory path is replaced
        # with '$HOME' in config.py).
        defaults[ 'output'   ] = re.sub( '\$HOME/', '', self.stdout_file )
        defaults[ 'error'    ] = re.sub( '\$HOME/', '', self.stderr_file )

        # NOTE ON SHELL DIRECTIVE: on AIX at NIWA '#@ shell = /bin/bash'
        # results in the job executing in a non-login shell (.profile
        # not sourced) whereas /bin/ksh does get a login shell. WTF?! In
        # any case this directive appears to affect only the shell *from
        # which the task job script is executed*, NOT the shell *in which it
        # is executed* (that is determined by the '#!' at the top of the
        # task job script).
        defaults[ 'shell'    ] = '/bin/ksh'

        # NOTE if the initial "running dir" does not exist (or is not
        # writable by the user?) loadleveler will hold the job. Use
        # the 'initialdir' directive to fix this.

        # In case the user wants to override the above defaults:
        for d,val in self.jobconfig['directives'].items():
            defaults[ d ] = val
        self.jobconfig['directives'] = defaults

    def construct_jobfile_submission_command( self ):
        command_template = self.job_submit_command_template
        if not command_template:
            command_template = self.__class__.COMMAND_TEMPLATE
        self.command = command_template % ( self.jobfile_path )

