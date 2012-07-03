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

class pbs( job_submit ):
    """
PBS qsub job submission.
    """

    COMMAND_TEMPLATE = "qsub %s"

    def set_directives( self ):
        self.directive_prefix = "#PBS"
        self.final_directive  = None
        self.directive_connector = " "

        defaults = {}
        defaults[ '-N' ] = self.task_id
        # Replace literal '$HOME' in stdout and stderr file paths with '' 
        # because environment variables are not interpreted in directives.
        # (For remote tasks the local home directory path is replaced
        # with '$HOME' in config.py).
        defaults[ '-o' ] = re.sub( '\$HOME/', '', self.stdout_file )
        defaults[ '-e' ] = re.sub( '\$HOME/', '', self.stderr_file )

        # In case the user wants to override the above defaults:
        for d in self.directives:
            defaults[ d ] = self.directives[ d ]
        # PBS requires jobs names <= 15 characters
        # This restriction has been removed at PBS version 11
        # but truncating to 15 chars should not cause any harm.
        if len( defaults[ '-N' ] ) > 15:
            defaults[ '-N' ] = defaults[ '-N' ][:15]
        self.directives = defaults

    def construct_jobfile_submission_command( self ):
        command_template = self.job_submit_command_template
        if not command_template:
            command_template = self.COMMAND_TEMPLATE
        self.command = command_template % ( self.jobfile_path )
