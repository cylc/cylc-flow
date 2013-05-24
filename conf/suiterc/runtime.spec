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

#_______________________________________________________________________
#            THIS IS THE CYLC SUITE.RC SPECIFICATION FILE
#-----------------------------------------------------------------------
# Entries are documented in suite.rc reference in the Cylc User Guide. 

# _________________________________________________________MAIN SECTIONS
# [cylc]          - non task-related suite config.
# [scheduling]    - determines when tasks are ready to run.
# [runtime]       - how, where, what to execute when a task is ready.
# [visualization] - for suite graphing and the gcontrol graph view.

#_______________________________________________________________________
# WARNING: a CONFIGOBJ or VALIDATE bug? list constructor fails if final
# element is followed by a space (or does it just need a trailing comma?):
#   GOOD: foo = string_list( default=list('foo','bar'))
#   BAD:  bar = string_list( default=list('foo','bar' ))

# RUNTIME ITEMS ARE NO LONGER VALIDATED AS A MATTER OF COURSE, BECAUSE
# VALIDATION FLESHES OUT THE FULL DATA STRUCTURE BELOW. The configobj
# validation process also coerces non-string values to their intended
# types, so we now do this manually in config.py:coerce_runtime_values()
# WHICH MUST BE KEPT UP TO DATE WITH CHANGES IN THIS FILE.

[runtime]
    [[__many__]]
        inherit = force_list( default=list() )
        title = string( default="No title provided" )
        description = string( default="No description provided" )
        initial scripting = string( default=None )
        environment scripting = string( default=None )
        pre-command scripting = string( default=None )
        command scripting = string( default='echo Default command scripting; sleep $(cylc rnd 1 16)')
        post-command scripting = string( default=None )
        retry delays = force_list( default=list() )
        manual completion = boolean( default=False )
        extra log files = force_list( default=list())
        enable resurrection = boolean( default=False )
        work sub-directory = string( default=$CYLC_TASK_ID )
        [[[simulation mode]]]
            run time range = list( default=list(1,16))
            simulate failure = boolean( default=False )
            disable task event hooks = boolean( default=True )
            disable retries = boolean( default=True )
        [[[dummy mode]]]
            command scripting = string( default='echo Dummy command scripting; sleep $(cylc rnd 1 16)')
            disable pre-command scripting = boolean( default=True )
            disable post-command scripting = boolean( default=True )
            disable task event hooks = boolean( default=True )
            disable retries = boolean( default=True )
        [[[job submission]]]
            method = string( default=background )
            command template = string( default=None )
            shell = string( default='/bin/bash' )
            retry delays = force_list( default=list() )
        [[[remote]]]
            host = string( default=None )
            owner = string( default=None )
            # This should really be host-specific in the suite
            # definition; but currently no other items warrant a top
            # level [host] section:
            suite definition directory = string( default=None )
        [[[event hooks]]]
            submitted handler = string( default=None )
            started handler = string( default=None )
            succeeded handler = string( default=None )
            failed handler = string( default=None )

            submission failed handler = string( default=None )
            warning handler = string( default=None )
            retry handler = string( default=None )
            submission retry handler = string( default=None )

            submission timeout handler = string( default=None )
            submission timeout = float( default=None )

            execution timeout handler = string( default=None )
            execution timeout = float( default=None )

            reset timer = boolean( default=False )

        [[[environment]]]
            __many__ = string
        [[[directives]]]
            __many__ = string
        [[[outputs]]]
            __many__ = string


