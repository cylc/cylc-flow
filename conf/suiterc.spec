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
tasks to include at startup = force_list( default=list() )

runahead limit in hours = integer( min=0, default=24 )

suite log directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME/log/suite' )
roll log at startup = boolean( default=True )

state dump directory = string( default = string( default='$HOME/cylc-run/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME/state' )
number of state dump backups = integer( min=1, default=10 )

use quick task elimination = boolean( default=True )
simulation mode only = boolean( default=False )
allow multiple simultaneous instances = boolean( default=False )
UTC mode = boolean( default=False )

[special tasks]
    clock-triggered = force_list( default=list())
    startup = force_list( default=list())
    cold start = force_list( default=list())
    sequential = force_list( default=list())
    one off = force_list( default=list())
    models with explicit restart outputs = force_list( default=list())

[task families]
    __many__ = force_list( default=None )

[dependencies]
    graph = string( default=None )
    [[__many__]]
    graph = string
    daemon = string( default=None )

[task run time]
    [[root]]
        inherit = string( default=None )
        description = string( default="No description supplied" )
        command = force_list( default=list( "echo DUMMY $TASK_ID; sleep $CYLC_SIMULATION_SLEEP",))

        job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
        job submission command template = string( default=None )
        job submission shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=/bin/bash )
        job submission log directory = string( default='$HOME/cylc-run/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME/log/job' )

        owner = string( default=None )
        owned task execution method = option( sudo, ssh, default=sudo )
        ignore task owners = boolean( default=False )

        remote host = string( default=None )
        remote cylc directory = string( default=None )
        remote suite directory = string( default=None )
        remote shell template = string( default='ssh -oBatchMode=yes %s' )

        task submitted hook script = string( default=None )
        task submission failed hook script = string( default=None )
        task started hook script = string( default=None )
        task succeeded hook script = string( default=None )
        task failed hook script = string( default=None )
        task warning hook script = string( default=None )
        task timeout hook script = string( default=None )

        task submission timeout in minutes = float( default=None )
        task execution timeout in minutes = float( default=None )
        reset execution timeout on incoming messages = boolean( default=None )

        extra log files = force_list( default=list())

        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )

        manual task completion messaging = boolean( default=False )

        hours = force_list( default=list())

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

        job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
        job submission command template = string( default=None )
        job submission shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=None )
        job submission log directory = string( default=None )


        owner = string( default=None )
        owned task execution method = option( sudo, ssh, default=None )
        ignore task owners = boolean( default=None )

        remote host = string( default=None )
        remote cylc directory = string( default=None )
        remote suite directory = string( default=None )
        remote shell template = string( default=None )

        task submitted hook script = string( default=None )
        task submission failed hook script = string( default=None )
        task started hook script = string( default=None )
        task succeeded hook script = string( default=None )
        task failed hook script = string( default=None )
        task warning hook script = string( default=None )
        task timeout hook script = string( default=None )

        task submission timeout in minutes = float( default=None )
        task execution timeout in minutes = float( default=None )
        reset execution timeout on incoming messages = boolean( default=None )

        extra log files = force_list( default=list())

        pre-command scripting = string( default=None )
        post-command scripting = string( default=None )

        manual task completion messaging = boolean( default=None )

        hours = force_list( default=list())

        [[[environment]]]
            __many__ = string

        [[[directives]]]
            __many__ = string

        [[[outputs]]]
            __many__ = string

[simulation mode]
    clock offset from initial cycle time in hours = integer( default=24 )
    clock rate in seconds per simulation hour = integer( default=10 )
    # exported as $CYLC_SIMULATION_SLEEP in job submission file:
    task run time in seconds = integer( default=10 )

[visualization]
    initial cycle time = integer( default=2999010100 )
    final cycle time = integer( default=2999010123 )
    show family members = boolean( default=False )
    # TO DO: USE SUB-GRAPH FOR FAMILY MEMBERS?
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

[cylc local environment]
    __many__ = string

[experimental]
    live graph movie = boolean( default=False )

# This section is for development purposes only and is ignored by
# document processing. It can be used to test new task proxy class
# developments without bothering with suite.rc graph parsing. New items
# may be added here for use in config.py:load_raw_task_definitions().
[raw task definitions]
    [[__many__]]
    description = string( default="No description supplied" )
    command = force_list( default=list( "echo DUMMY $TASK_ID; sleep $CYLC_SIMULATION_SLEEP",))
    job submission method = option( at_now, background, loadleveler, ll_ecox, ll_raw, ll_raw_ecox, default=None )
    job submission log directory = string( default=None )
    owner = string( default=None )
    remote host = string( default=None )
    remote cylc directory = string( default=None )
    remote suite directory = string( default=None )
    task submitted hook script = string( default=None )
    task submission failed hook script = string( default=None )
    task started hook script = string( default=None )
    task succeeded hook script = string( default=None )
    task failed hook script = string( default=None )
    task warning hook script = string( default=None )
    task timeout hook script = string( default=None )
    task submission timeout in minutes = float( default=None )
    task execution timeout in minutes = float( default=None )
    reset execution timeout on incoming messages = boolean( default=True )
    extra log files = force_list( default=list())
    #hours = force_list() # e.g. 0,6,12,18
    hours string = string(default=None)  # e.g. "0,6,12,18"
    manual task completion messaging = boolean( default=None )

    type = option( free, async_daemon, async_repeating, async_oneoff )
    asyncid pattern = string( default=None )

    # oneoff, sequential, tied, clocktriggered
    type modifiers = force_list( default=list() )

    clock trigger offset in hours = float( default=0.0 )

        [[[prerequisites]]]
        __many__ = string

        [[[startup prerequisites]]]
        __many__ = string

        [[[environment]]]
        __many__ = string
        [[[directives]]]
        __many__ = string
        [[[outputs]]]
        __many__ = string

