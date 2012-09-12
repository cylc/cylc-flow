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

#___________________________________________________________________HEAD
title = string( default="No title provided" )
description = string( default="No description provided" )
#___________________________________________________________________CYLC
[cylc]
    UTC mode = boolean( default=False )
    required run mode = option( 'live','dummy','simulation', default=None )
    pyro connection timeout = float( min=0.0, default=None )
    maximum simultaneous job submissions = integer( min=1, default=50 )
    abort if any task fails = boolean( default=False )
    log resolved dependencies = boolean( default=False )
    [[logging]]
        directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_REG_NAME/log/suite' )
        roll over at start-up = boolean( default=True )
    [[state dumps]]
        directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_REG_NAME/state' )
        number of backups = integer( min=1, default=10 )
    [[lockserver]]
        enable = boolean( default=False )
        simultaneous instances = boolean( default=False )
    [[environment]]
        __many__ = string
    [[event hooks]]
        startup handler = string( default=None )
        timeout handler = string( default=None )
        shutdown handler = string( default=None ) 
        timeout = float( default=None )
        reset timer = boolean( default=False )
        abort if startup handler fails = boolean( default=False )
        abort if shutdown handler fails = boolean( default=False )
        abort if timeout handler fails = boolean( default=False )
        abort on timeout = boolean( default=False )
    [[simulation mode]]
        disable suite event hooks = boolean( default=True )
    [[dummy mode]]
        disable suite event hooks = boolean( default=True )
    [[accelerated clock]]
        disable = boolean( default=False )
        rate = integer( default=10 )
        offset = integer( default=24 )
    [[reference test]]
        suite shutdown event handler = string( default='cylc hook check-triggering' )
        required run mode = option( 'live', 'simulation', 'dummy', default=None )
        allow task failures = boolean( default=False )
        expected task failures = force_list( default=list() )
        live mode suite timeout = float( default=None )
        dummy mode suite timeout = float( default=None )
        simulation mode suite timeout = float( default=None )
#_____________________________________________________________SCHEDULING
[scheduling]
    initial cycle time = integer( default=None )
    final cycle time = integer( default=None )
    cycling = string( default="HoursOfTheDay" ) 
    runahead limit = integer( min=0, default=None )
    [[queues]]
        [[[default]]]
            # for all non queue-assigned tasks
            limit = integer( default=0)
        [[[__many__]]]
            limit = integer( default=0 )
            members = force_list( default=list())
    [[special tasks]]
        clock-triggered = force_list( default=list())
        start-up = force_list( default=list())
        cold-start = force_list( default=list())
        sequential = force_list( default=list())
        one-off = force_list( default=list())
        explicit restart outputs = force_list( default=list())
        exclude at start-up = force_list( default=list())
        include at start-up = force_list( default=list())
    [[dependencies]]
        graph = string( default=None )
        [[[__many__]]]
            graph = string( default=None )
            daemon = string( default=None )
#________________________________________________________________RUNTIME
[runtime]
    [[root]]
        inherit = string( default=None )
        description = string( default="No description provided" )
        initial scripting = string( default=None )
        environment scripting = string( default=None )
        command scripting = string( default='echo Default command scripting; sleep $(cylc rnd 1 16)')
        retry delays = force_list( default=list() )
        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )
        manual completion = boolean( default=False )
        extra log files = force_list( default=list())
        enable resurrection = boolean( default=False )
        log directory = string( default='$HOME/cylc-run/$CYLC_SUITE_REG_NAME/log/job' )
        share directory = string( default='$CYLC_SUITE_DEF_PATH/share' )
        work directory = string( default='$CYLC_SUITE_DEF_PATH/work/$CYLC_TASK_ID' )
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
        [[[remote]]]
            host = string( default=None )
            owner = string( default=None )
            cylc directory = string( default=None )
            suite definition directory = string( default=None )
            remote shell template = string( default='ssh -oBatchMode=yes %s' )
            log directory = string( default=None )
            share directory = string( default=None )
            work directory = string( default=None )
            ssh messaging = boolean( default=False )
        [[[event hooks]]]
            submitted handler = string( default=None )
            started handler = string( default=None )
            succeeded handler = string( default=None )
            failed handler = string( default=None )

            submission failed handler = string( default=None )
            warning handler = string( default=None )
            retry handler = string( default=None )

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

    [[__many__]]
        inherit = string( default=root )
        description = string( default=None )
        initial scripting = string( default=None )
        command scripting = string( default=None )
        fail in simulation mode = boolean( default=None )
        retry delays = force_list( default=list() )
        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )
        manual completion = boolean( default=None )
        extra log files = force_list( default=list())
        enable resurrection = boolean( default=None )
        log directory = string( default=None )
        share directory = string( default=None )
        work directory = string( default=None )
        [[[simulation mode]]]
            run time range = list( default=list() )
            simulate failure = boolean( default=None )
            disable task event hooks = boolean( default=None )
            disable retries = boolean( default=None )
        [[[dummy mode]]]
            command scripting = string( default=None )
            disable pre-command scripting = boolean( default=None )
            disable post-command scripting = boolean( default=None )
            disable task event hooks = boolean( default=None )
            disable retries = boolean( default=None )
        [[[job submission]]]
            method = string( default=None )
            command template = string( default=None )
            shell = string( default=None )
        [[[remote]]]
            host = string( default=None )
            owner = string( default=None )
            cylc directory = string( default=None )
            suite definition directory = string( default=None )
            scripting = string( default=None )
            remote shell template = string( default=None )
            log directory = string( default=None )
            share directory = string( default=None )
            work directory = string( default=None )
            ssh messaging = boolean( default=None )
        [[[event hooks]]]
            submitted handler = string( default=None )
            started handler = string( default=None )
            succeeded handler = string( default=None )
            failed handler = string( default=None )

            submission failed handler = string( default=None )
            warning handler = string( default=None )
            retry handler = string( default=None )

            submission timeout handler = string( default=None )
            submission timeout = float( default=None )

            execution timeout handler = string( default=None )
            execution timeout = float( default=None )

            reset timer = boolean( default=None )
        [[[environment]]]
            __many__ = string
        [[[directives]]]
            __many__ = string
        [[[outputs]]]
            __many__ = string
#__________________________________________________________VISUALIZATION
[visualization]
    initial cycle time = integer( default=None )
    final cycle time = integer( default=None )
    collapsed families = force_list( default=list() )
    use node color for edges = boolean( default=True )
    use node color for labels = boolean( default=False )
    default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=box'))
    default edge attributes = force_list( default=list('color=black'))
    enable live graph movie = boolean( default=False )
    [[node groups]]
        __many__ = force_list( default=list())
    [[node attributes]]
        __many__ = force_list( default=list())
    [[runtime graph]]
        enable = boolean( default=False )
        cutoff = integer( default=24 )
        directory = string( default='$CYLC_SUITE_DEF_PATH/graphing')
#____________________________________________________________DEVELOPMENT
[development]
    use quick task elimination = boolean( default=True )

