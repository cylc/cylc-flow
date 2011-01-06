title = string( default="No suite title given" )
description = string( default="No suite description supplied" )
allow multiple simultaneous suite instances = boolean( default=False )
maximum runahead hours = integer( min=0, default=24 )
number of state dump backups = integer( min=1, default=10 )
job submission method = option( at_now, background, ll_raw, ll_basic, ll_basic_eco, default=background )
job submission log directory = string( default='' )
logging level = option( debug, info, warning, error, critical, default=info )
task failure hook script = string( default=None )
task submit failure hook script = string( default=None )

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
