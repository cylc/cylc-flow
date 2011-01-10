title = string( default="No suite title given" )
description = string( default="No suite description supplied" )
allow multiple simultaneous suite instances = boolean( default=False )
maximum runahead hours = integer( min=0, default=24 )
number of state dump backups = integer( min=1, default=10 )
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
job submission log directory = string( default='' )
logging level = option( debug, info, warning, error, critical, default=info )
ignore task owners = boolean( default=False )

task submitted hook = string( default=None )
task started hook = string( default=None )
task finished hook = string( default=None )
task failed hook = string( default=None )
task submission failed hook = string( default=None )

task timeout hook = string( default=None )
task submission timeout minutes = float( default=None )

include task list   = string_list( default=list() )
exclude task list   = string_list( default=list() )

job log directory = string( default='' )

[ task families ]
    __many__ = string_list( default=None )

[ dependency graph ]
    [[ __many__ ]]
    __many__ = string

[ task insertion groups ]
 __many__ = string_list()

[ environment ]
__many__ = string

# NOTE CONFIGOBJ or VALIDATE BUG: LIST CONSTRUCTOR FAILS IF LAST LIST
# ELEMENT IS FOLLOWED BY A SPACE:
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
    command list = string_list( default=list('cylc-wrapper /bin/true'))
    owner = string( default=None )
    host = string( default=None )
        [[[ environment ]]]
        __many__ = string
        [[[ directives ]]]
        __many__ = string
        [[[ scripting ]]]
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
    command list = string_list( default=list('cylc-wrapper /bin/true'))
    intercycle = boolean( default=False )
    job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=None)
    host = string( default=None )
    owner = string( default=None )
    follow on task = string( default=None )
    execution timeout minutes = float( default=None )
    reset execution timeout on incoming messages = boolean( default=True )

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

        [[[outputs]]]
        ___many___ = string
            [[[[__many__]]]]  # CYCLE TIME LIST
            __many__ = string

        [[[coldstart prerequisites]]]
        ___many___ = string
            [[[[__many__]]]]  # CYCLE TIME LIST
            __many__ = string

        [[[suicide prerequisites]]]
        ___many___ = string
            [[[[__many__]]]]  # CYCLE TIME LIST
            __many__ = string

    #    [[[ scripting ]]]
    #    __many__ = string
    # OR?
    # scripting = string()
