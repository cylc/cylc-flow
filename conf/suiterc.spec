title = string( default="No suite title supplied" )
description = string( default="No suite description supplied" )

# declare all suite I/O relative to $HOME (not used yet)
# user portable = boolean( default=False )

# for demo suites that have no real task implementation
dummy mode only = boolean( default=False )

# declare all I/O unique by suite registration (i.e. all I/O paths include 
# either $CYLC_SUITE or $CYLC_SUITE_GROUP and $CYLC_SUITE_NAME:

allow multiple simultaneous suite instances = boolean( default=False )

maximum runahead hours = integer( min=0, default=24 )

number of state dump backups = integer( min=1, default=10 )

job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
owned task execution method = option( sudo, ssh, default=sudo )

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

# directories: absolute path, but can use ~user, env vars ($HOME etc.):
top level state dump directory = string( default = '$HOME/.cylc/state' )
top level logging directory = string( default = '$HOME/.cylc/logging' )
# for owned tasks, the suite owner's homedir is replaced by task owner's.
job submission log directory = string( default='$HOME/CylcJobLogs/$CYLC_SUITE_GROUP/$CYLC_SUITE_NAME' )

# script to call whenever a task is submitted
task submitted hook = string( default=None )
# script to call whenever a task reports it has started
task started hook = string( default=None )
# script to call whenever a task finishes successfully
task finished hook = string( default=None )
# script to call whenever a task reports failed
task failed hook = string( default=None )
# script to call whenever  a task emits a warning
task warning hook = string( default=None )
# script to call whenever the initial job submission for a task fails
task submission failed hook = string( default=None )
# script to call whenever a task times out (job submission or execution)
task timeout hook = string( default=None )
# call 'task timeout hook' script if submitted task does not start after
# N minutes
task submission timeout minutes = float( default=None )
task execution timeout minutes = float( default=None )

tasks to include at startup = force_list( default=list())
tasks to exclude at startup = force_list( default=list())

# global scripting section
pre-command scripting = string( default='' )
post-command scripting = string( default='' )
 
[dummy mode]
# dummy mode was most useful prior to cylc-3: it allowed us to get the
# scheduling right without running real tasks when a suite was defined
# entirely by a collection of distinct "task definition files" whose
# prerequisites and outputs had to be consistent across the suite.
# Now (post cylc-3) it is primarily useful for cylc development, and
# for generating run-time dependency graphs very quickly.
clock offset from initial cycle time in hours = integer( default=24 )
clock rate in seconds per dummy hour = integer( default=10 )
# exported as $CYLC_DUMMY_SLEEP in job submission file:
task run time in seconds = integer( default=10 )
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )

[special tasks]
    startup = force_list( default=list())
    coldstart = force_list( default=list())
    oneoff = force_list( default=list())
    sequential = force_list( default=list())
    clock-triggered = force_list( default=list())
    # outputs MUST contain the word 'restart':
    models with explicit restart outputs = force_list( default=list())

[task families]
    __many__ = force_list( default=None )

[dependencies]
    # dependency graphs under cycle time lists:
    [[__many__]]
    graph = string

[experimental]
# generate a distinct graph for each timestep
live graph movie = boolean( default=False )

[visualization]
# hours after which to stop plotting the run time graph
when to stop updating = integer( default=24 )
# absolute, or relative to $CYLC_SUITE_DIR for portability
run time graph directory = string( default='$CYLC_SUITE_DIR/graphing')
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

[task insertion groups]
 __many__ = force_list()

[environment]
__many__ = string

# CONFIGOBJ or VALIDATE BUG? LIST CONSTRUCTOR FAILS IF LAST LIST ELEMENT
# IS FOLLOWED BY A SPACE (OR DOES IT JUST NEED A TRAILING COMMA?):
#   GOOD:
# foo = string_list( default=list('foo','bar'))
#   BAD:
# bar = string_list( default=list('foo','bar' ))

[tasks]
    # new style suite definition: dependency graph plus minimal task info
    [[__many__]]
    description = string( default="No task description supplied" )
    job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=None)
    task submitted hook = string( default=None )
    task started hook = string( default=None )
    task finished hook = string( default=None )
    task failed hook = string( default=None )
    task warning hook = string( default=None )
    task submission failed hook = string( default=None )
    task timeout hook = string( default=None )
    task submission timeout minutes = float( default=None )
    execution timeout minutes = float( default=None )
    reset execution timeout on incoming messages = boolean( default=True )
    pre-command scripting = string( default='' )
    post-command scripting = string( default='' )
    # default to dummy task:
    command = force_list( default=list( cylc wrap -m "echo DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP",))
    owner = string( default=None )
    host = string( default=None )
    # hours required to use ('submit' or 'insert') tasks not in the
    # graph; if present graphed hours must not conflict with this.
    hours = force_list( default=list())
    extra log files = force_list( default=list())
        [[[environment]]]
        __many__ = string
        [[[directives]]]
        __many__ = string
          [[[outputs]]]
        __many__ = string
