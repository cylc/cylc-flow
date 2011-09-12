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

# THIS SPEC FILE DEFINES ALL LEGAL ENTRIES IN CYLC SUITE.RC FILES.

# NOTE: A CONFIGOBJ or VALIDATE BUG? LIST CONSTRUCTOR FAILS IF LAST LIST
# ELEMENT IS FOLLOWED BY A SPACE (OR DOES IT JUST NEED A TRAILING COMMA?):
#   GOOD:
# foo = string_list( default=list('foo','bar'))
#   BAD:
# bar = string_list( default=list('foo','bar' ))

title = string( default="No title supplied" )
description = string( default="No description supplied" )

initial cycle time = integer( default=None )
final cycle time = integer( default=None )

use lockserver = boolean( default=False )
use secure passphrase = boolean( default=False )

tasks to exclude at startup = force_list( default=list())
tasks to include at startup = force_list( default=list())

runahead limit in hours = integer( min=0, default=24 )

suite log directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_REG/log/suite' )
roll log at startup = boolean( default=True )

state dump directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_REG/state' )
number of state dump backups = integer( min=1, default=10 )

simulation mode only = boolean( default=False )
allow multiple simultaneous instances = boolean( default=False )
UTC mode = boolean( default=False )

[scheduling]
    [[special task types]]
        clock-triggered = force_list( default=list())
        start-up = force_list( default=list())
        cold-start = force_list( default=list())
        sequential = force_list( default=list())
        one-off = force_list( default=list())
        tasks with explicit restart outputs = force_list( default=list())

    [[dependencies]]
        graph = string( default=None )
        [[[__many__]]]
            graph = string( default=None )
            daemon = string( default=None )

[runtime]
    [[root]]
        inherit = string( default=None )
        description = string( default="No description supplied" )
        command = force_list( default=list( "echo THIS is the root DUMMY command for $TASK_ID; sleep 10",))
        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )
        manual task completion messaging = boolean( default=False )
        hours = force_list( default=list())
        extra log files = force_list( default=list())
        [[[job submission]]]
            method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=background )
            command template = string( default=None )
            job script shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=/bin/bash )
            log directory = string( default='$HOME/cylc-run/$CYLC_SUITE_REG/log/job' )
            # This log directory is used for the task job script for local and remote
            # tasks, and also for the task stdout and stderr logs for local tasks.
            # All environment variables are interpolated out before use.
            # Remote tasks must also define a [[[remote]]] log directory. 
        [[[remote]]]
            host = string( default=None )
            owner = string( default=None )
            cylc directory = string( default=None )
            suite definition directory = string( default=None )
            remote shell template = string( default='ssh -oBatchMode=yes %s' )
            log directory = string( default=None )
            # This log directory is used for task job script and stdout
            # and stderr logs for remote tasks. Suite identity variables
            # will be interpolated out locally before use, but other
            # environment variables (such as $HOME) are left alone for
            # interpolation on the remote host. Whether or not you can
            # use (non suite identity) environment variables thus
            # depends on the job submission method. For submission via
            # loadleveler, for example, the stdout and stderr paths have
            # to be written as directives to the job script prior to 
            # submission, and loadleveler does not interpolate
            # environment variables in its job directives.
        [[[event hooks]]]
            submitted script = string( default=None )
            submission failed script  = string( default=None )
            started script = string( default=None )
            succeeded script = string( default=None )
            failed script = string( default=None )
            warning script = string( default=None )
            timeout script = string( default=None )
            submission timeout in minutes = float( default=None )
            execution timeout in minutes = float( default=None )
            reset execution timeout on incoming messages = boolean( default=False )
        [[[environment]]]
            __many__ = string
        [[[directives]]]
            __many__ = string
        [[[outputs]]]
            __many__ = string

    [[__many__]]
        inherit = string( default=root )
        description = string( default=None )
        command = force_list( default=None )
        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )
        manual task completion messaging = boolean( default=None )
        hours = force_list( default=list())
        extra log files = force_list( default=list())
        [[[job submission]]]
            method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
            command template = string( default=None )
            job script shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=None )
            log directory = string( default=None )
        [[[remote]]]
            host = string( default=None )
            owner = string( default=None )
            cylc directory = string( default=None )
            suite definition directory = string( default=None )
            remote shell template = string( default=None )
            log directory = string( default=None )
        [[[event hooks]]]
            submitted script = string( default=None )
            submission failed script  = string( default=None )
            started script = string( default=None )
            succeeded script = string( default=None )
            failed script = string( default=None )
            warning script = string( default=None )
            timeout script = string( default=None )
            submission timeout in minutes = float( default=None )
            execution timeout in minutes = float( default=None )
            reset execution timeout on incoming messages = boolean( default=None )
        [[[environment]]]
            __many__ = string
        [[[directives]]]
            __many__ = string
        [[[outputs]]]
            __many__ = string

[simulation mode]
    clock offset from initial cycle time in hours = integer( default=24 )
    clock rate in seconds per simulation hour = integer( default=10 )
    command = force_list( default=list( "echo SIMULATION MODE $TASK_ID; sleep 10; echo BYE",))
    failure command = force_list( default=list( "echo SIMULATION MODE $TASK_ID; sleep 10; echo ABORTING; /bin/false",))
    job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=background )

[visualization]
    initial cycle time = integer( default=2999010100 )
    final cycle time = integer( default=2999010123 )
    collapsed families = force_list( default=list() )
    use node color for edges = boolean( default=True )
    default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=box'))
    default edge attributes = force_list( default=list('color=black'))
    [[node groups]]
        __many__ = force_list( default=list())
    [[node attributes]]
        __many__ = force_list( default=list())

    [[run time graph]]
        enable = boolean( default=False )
        cutoff in hours = integer( default=24 )
        directory = string( default='$CYLC_SUITE_DIR/graphing')

[task insertion groups]
    __many__ = force_list()

[scheduler environment]
    __many__ = string

[development]
    use quick task elimination = boolean( default=True )
    live graph movie = boolean( default=False )
