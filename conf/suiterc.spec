title = string( default="No suite title given" )
description = string( default="No suite description supplied" )
allow multiple simultaneous suite instances = boolean( default=False )
maximum runahead hours = integer( min=0, default=24 )
number of state dump backups = integer( min=1, default=10 )
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
job submission log directory = string( default='' )
ignore task owners = boolean( default=False )
use crude safety lock = boolean( default=False )
use secure passphrase = boolean( default=False )

use lockserver = boolean( default=False )
use quick task elimination = boolean( default=True )

# absolute or relative to $HOME:
top level state dump directory = string( default = 'cylc/state' )
top level logging directory = string( default = '.cylc/logging' )

task submitted hook = string( default=None )
task started hook = string( default=None )
task finished hook = string( default=None )
task failed hook = string( default=None )
task warning hook = string( default=None )
task submission failed hook = string( default=None )

task timeout hook = string( default=None )
task submission timeout minutes = float( default=None )

include task list   = string_list( default=list())
exclude task list   = string_list( default=list())
coldstart task list = string_list( default=list())

[ dummy mode ]
clock offset from initial cycle time in hours = integer( default=24 )
clock rate in seconds per dummy hour = integer( default=10 )
# exported as $CYLC_DUMMY_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
command      = string( default='cylc-wrapper -m "echo DUMMY MODE $TASK_ID; sleep $CYLC_DUMMY_SLEEP"')
command fail = string( default='cylc-wrapper -m "echo DUMMY MODE FAILOUT $TASK_ID; /bin/false"')
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )

[ task families ]
    __many__ = string_list( default=None )

[ dependency graph ]
    [[ __many__ ]]
    __many__ = string

[visualization]
use node color for edges = boolean( default=True )
task families in subgraphs = boolean( default=True )
default node attributes = string( default='style=filled, fillcolor=gray, color=blue, shape=ellipse')
default edge attributes = string( default='color=black, style=bold')
    [[label node attributes]]
    __many__ = string

[ task insertion groups ]
 __many__ = string_list()

[ environment ]
__many__ = string

# CONFIGOBJ or VALIDATE BUG? LIST CONSTRUCTOR FAILS IF LAST LIST ELEMENT
# IS FOLLOWED BY A SPACE (OR DOES IT JUST NEED A TRAILING COMMA?):
#   GOOD:
# foo = string_list( default=list('foo','bar'))
#   BAD:
# bar = string_list( default=list('foo','bar' ))

[ tasks ]
    # new style suite definition: dependency graph plus minimal task info
    [[ __many__ ]]
    description = string( default="No task description supplied" )
    job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=None)
    type = string( default=free)
    execution timeout minutes = float( default=None )
    reset execution timeout on incoming messages = boolean( default=True )
    type modifier list = string_list( default=list())
    # default to dummy task:
    command list = string_list( default=list( cylc-wrapper -m "echo DUMMY MODE $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
    owner = string( default=None )
    host = string( default=None )
    intercycle = boolean( default=False )
    scripting = string( default='' )
    log file list = string_list( default=list())
        [[[ environment ]]]
        __many__ = string
        [[[ directives ]]]
        __many__ = string
          [[[ outputs ]]]
        __many__ = string

[ taskdefs ]
    # old style suite definition: a collection of task proxies.
    [[ __many__ ]]  # TASK NAME
    description = string( default="No task description supplied" )
    type = string( default=free)
    type modifier list = string_list( default=list())
    cycles = int_list()   # CYCLE TIME LIST
    # default to dummy task:
    command list = string_list( default=list( cylc-wrapper -m "echo DUMMY MODE $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
    intercycle = boolean( default=False )
    job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=None)
    host = string( default=None )
    owner = string( default=None )
    follow on task = string( default=None )
    execution timeout minutes = float( default=None )
    reset execution timeout on incoming messages = boolean( default=True )
    scripting = string( default='' )
    log file list = string_list( default=list())
        [[[ environment ]]]
        __many__ = string

        [[[ directives ]]]
        __many__ = string

        [[[ prerequisites ]]]
        ___many___ = string
        condition = string( default=None )

            [[[[__many__]]]]  # CYCLE TIME LIST
            __many__ = string
            condition = string( default=None )

        [[[coldstart prerequisites]]]
        ___many___ = string
            [[[[__many__]]]]  # CYCLE TIME LIST
            __many__ = string

        [[[suicide prerequisites]]]
        ___many___ = string
            [[[[__many__]]]]  # CYCLE TIME LIST
            __many__ = string

        [[[outputs]]]
        ___many___ = string
            [[[[__many__]]]]  # CYCLE TIME LIST
            __many__ = string
