#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

from cylc import which
import os, re
from job_submit import job_submit

# TODO - THIS CLASS NEEDS TO BE CHECKED AND EITHER UPDATED (for job poll
# and kill - probably just derive from the main loadleveler class) OR
# REMOVED. It was used a long time ago for submitting existing
# job-scripts with built-in loadleveler directives.

class ll_raw( job_submit ):

    def write_jobfile( self, JOBFILE ):
        # get full path of task script (it could be defined relative
        # to suite scripts dir in the taskdef file).
        orig_file = which.which( self.task )

        # read original and count '#@ queue' directives, in case is
        # a multiple step loadleveler job
        queue_re = re.compile( '^\s*#\s*@\s*queue\s*$') 
        FILE = open( orig_file, 'r' )
        lines = FILE.readlines()
        FILE.close()
        n_queue_directives = len( filter( queue_re.search, lines ) )

        # write original out to the jobfile line by line
        # inserting cylc environment etc. when we reach the final
        # queue directive.
        done = False
        count = 0
        for line in lines:
            line.strip()
            JOBFILE.write( line )
            if re.match( '^\s*#\s*@\s*queue\s*$', line ):
                count += 1
                if not done and count == n_queue_directives:
                    self.write_environment( JOBFILE ) 
                    self.write_cylc_scripting( JOBFILE )
                    self.write_extra_scripting( JOBFILE )
                    done = True

    def construct_command( self ):
        self.command = 'llsubmit ' + self.jobfile_path

