title = string( default="No suite title given" )
description = string( default="No suite description supplied" )
allow multiple simultaneous suite instances = boolean( default=False )
maximum runahead hours = integer( min=0, default=24 )
number of state dump backups = integer( min=1, default=10 )
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
job submission log directory = string( default='' )
logging level = option( debug, info, warning, error, critical, default=info )

task submitted hook = string( default=None )
task started hook = string( default=None )
task finished hook = string( default=None )
task failed hook = string( default=None )
task submission failed hook = string( default=None )

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
    type list = string_list( default=list('free'))
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
    [[ __many__ ]]
    #intercycle = boolean( default=False )
    description = string( default="No task description supplied" )
    #job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=None)
    #type list = string_list( default=list('free'))
    cycles = integer_list()
    #command list = string_list( default=list('cylc-wrapper /bin/true'))
    #host = string( default=None )
    #owner = string( default=None )
    #follow on task = string( default=None )

    #prerequisites = string_list( default=list())
    #outputs = string_list( default=list())
    #coldstart prerequisites = string_list( default=list())
    #suicide prerequisites = string_list( default=list())
    # TO DO: conditional prerequisites

    #    [[[ scripting ]]]
    #    __many__ = string
    # OR?
    # scripting = string()

        #[[[ ___many___ ]]] # specific cycles
        #prerequisites = string_list( default=list())
        #outputs = string_list( default=list())
        #coldstart prerequisites = string_list( default=list())
        #suicide prerequisites = string_list( default=list())
 
        #[[[ environment ]]]
        #__many__ = string

        #[[[ directives ]]]
        #__many__ = string
