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
# [scheduling]    - items affecting when a task is deemed ready to run.
# [runtime]       - what to execute (and how) when a task is ready.
# [visualization] - for suite graphing and the graph-based control GUI.

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
    simulation mode only = boolean( default=False )
    pyro connection timeout = float( min=0.0, default=None )
    maximum simultaneous job submissions = integer( min=1, default=50 )
    abort if any task fails = boolean( default=False )
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
    [[simulation mode]]
        clock offset = integer( default=24 )
        clock rate = integer( default=10 )
        command scripting = string( default="echo SIMULATION MODE; sleep $CYLC_TASK_DUMMY_RUN_LENGTH")
        retry delays = force_list( default=list() )
        [[[event hooks]]]
            enable = boolean( default=False )
        [[[job submission]]]
            method = string( default=background )
    [[event hooks]]
        script = string( default=None )
        events = force_list( default=list() )
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
        command scripting = string( default='echo Dummy command scripting; sleep $CYLC_TASK_DUMMY_RUN_LENGTH')
        retry delays = force_list( default=list() )
        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )
        manual completion = boolean( default=False )
        extra log files = force_list( default=list())
        enable resurrection = boolean( default=False )
        [[[job submission]]]
            method = string( default=background )
            command template = string( default=None )
            shell = string( default='/bin/bash' )
            log directory = string( default='$HOME/cylc-run/$CYLC_SUITE_REG_NAME/log/job' )
            share directory = string( default='$CYLC_SUITE_DEF_PATH/share' )
            work directory = string( default='$CYLC_SUITE_DEF_PATH/work/$CYLC_TASK_ID' )
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
            script = string( default=None )
            events = force_list( default=list() )
            submission timeout = float( default=None )
            execution timeout = float( default=None )
            reset timer = boolean( default=False )
        [[[environment]]]
            CYLC_TASK_DUMMY_RUN_LENGTH = integer( default=10 )
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
        retry delays = force_list( default=list() )
        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )
        manual completion = boolean( default=None )
        extra log files = force_list( default=list())
        enable resurrection = boolean( default=None )
        [[[job submission]]]
            method = string( default=None )
            command template = string( default=None )
            shell = string( default=None )
            log directory = string( default=None )
            share directory = string( default=None )
            work directory = string( default=None )
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
            script = string( default=None )
            events = force_list( default=list() )
            submission timeout = float( default=None )
            execution timeout = float( default=None )
            reset timer = boolean( default=False )
        [[[environment]]]
            CYLC_TASK_DUMMY_RUN_LENGTH = integer( default=None )
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
    [[run time graph]]
        enable = boolean( default=False )
        cutoff = integer( default=24 )
        directory = string( default='$CYLC_SUITE_DEF_PATH/graphing')
#____________________________________________________________DEVELOPMENT
[development]
    use quick task elimination = boolean( default=True )

