
title = string( default="No suite title given" )
description = string( default="No suite description given" )
allow multiple simultaneous suite instances = boolean( default=False )
maximum runahead hours = integer( min=0, default=24 )
number of state dump backups = integer( min=1, default=10 )

coldstart task list = string_list( default=list() )
include task list   = string_list( default=list() )
exclude task list   = string_list( default=list() )
dummy out task list = string_list( default=list() )

job log directory = string( default='' )

[ dependency graph ]
__many__ = string


[ task insertion groups ]
 __many__ = string_list()

[ job submission ]
default method = string( default = 'background' )
    [[ overrides ]]
    tasks using background = string_list( default=list() )
    tasks using at now = string_list( default=list() )
    tasks using ll_raw = string_list( default=list() )
    tasks using ll_basic = string_list( default=list() )
    tasks using ll_basic_eco = string_list( default=list() )
    
[ environment ]
__many__ = string

[ tasks ]

    [[ __many__ ]]
    type = option( free, tied, default=free )
    number of restart outputs = integer( min=1, default=1 )
    type modifier list = string_list( default=list() )
    valid cycles = int_list( default=list( 0,6,12,18 ))
    command list = string_list( default=list('cylc-wrapper /bin/true'))

        [[[ environment ]]]
        __many__ = string

