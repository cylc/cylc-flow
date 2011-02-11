title = string( default="No suite title given" )
description = string( default="No suite description supplied" )
allow multiple simultaneous suite instances = boolean( default=False )
maximum runahead hours = integer( min=0, default=24 )
number of state dump backups = integer( min=1, default=10 )
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
# The chosen job submission shell affects the suite.rc environment and
# scripting sections; to allow Csh we'd just need to alter the hardwired
# exports for TASK_NAME, CYCLE_TIME, etc. appropriately.
job submission shell = option( /bin/bash, /usr/bin/bash, /bin/ksh, /usr/bin/ksh, default=/bin/bash )
roll scheduler log at startup = boolean( default=True )

ignore task owners = boolean( default=False )
use suite blocking = boolean( default=False )
use secure passphrase = boolean( default=False )

use lockserver = boolean( default=False )
use quick task elimination = boolean( default=True )

# absolute, or relative to $HOME:
top level state dump directory = string( default = 'cylc/state' )
top level logging directory = string( default = '.cylc/logging' )
job submission log directory = string( default='' )

task submitted hook = string( default=None )
task started hook = string( default=None )
task finished hook = string( default=None )
task failed hook = string( default=None )
task warning hook = string( default=None )
task submission failed hook = string( default=None )

task timeout hook = string( default=None )
task submission timeout minutes = float( default=None )

tasks to include at startup = force_list( default=list())
tasks to exclude at startup = force_list( default=list())

[ dummy mode ]
clock offset from initial cycle time in hours = integer( default=24 )
clock rate in seconds per dummy hour = integer( default=10 )
# exported as $CYLC_DUMMY_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )

[ special tasks ]
    startup = force_list( default=list())
    coldstart = force_list( default=list())
    oneoff = force_list( default=list())
    sequential = force_list( default=list())
    clock-triggered = force_list( default=list())

[ task families ]
    __many__ = force_list( default=None )

[ dependencies ]
    # dependency graphs under cycle time lists:
    [[ __many__ ]]
    graph = string

[experimental]
# suite monitoring via dependency graph
write live graph = boolean( default=False )
live graph movie = boolean( default=False )

# absolute, or relative to $CYLC_SUITE_DIR for portability
live graph directory path = string( default='graphing')

[visualization]
# hours after which to stop plotting the run time graph
when to stop updating = integer( default=24 )
# absolute, or relative to $CYLC_SUITE_DIR for portability
run time graph directory = string( default='graphing')
run time graph filename  = string( default='runtime.dot')
# TO DO: USE SUB-GRAPH FOR FAMILY MEMBERS
show family members = boolean( default=False )
use node color for edges = boolean( default=True )
default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=ellipse'))
default edge attributes = force_list( default=list('color=black'))

[[node groups]]
    __many__ = force_list( default=list())
[[node attributes]]
    # item is task name or task group name
    __many__ = force_list( default=list())

[ task insertion groups ]
 __many__ = force_list()

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
    execution timeout minutes = float( default=None )
    reset execution timeout on incoming messages = boolean( default=True )
    scripting = string( default='' )
    # default to dummy task:
    command = force_list( default=list( cylc wrap -m "echo DUMMY MODE $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
    owner = string( default=None )
    host = string( default=None )
    intercycle = boolean( default=False )
    extra log files = force_list( default=list())
        [[[ environment ]]]
        __many__ = string
        [[[ directives ]]]
        __many__ = string
          [[[ outputs ]]]
        __many__ = string
