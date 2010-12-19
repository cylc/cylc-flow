
# TO DO: ITEM NAME CHANGES

title = string( default="No suite description given" )

allow simultaneous instances = boolean( default=False )

maximum runahead = integer( min=0, default=24 )

state dump rolling archive length = integer( min=1, default=10 )

coldstart tasks = string_list( default=list() )

tasks included at startup = string_list( default=list() )

tasks excluded at startup = string_list( default=list() )

tasks to dummy out = string_list( default=list() )

job log directory = string( default='' )

[ dependency graph ]
__many__ = string


[ task insertion groups ]
 __many__ = string_list()

[ job submission ]
default = string( default = 'background' )
    [[ overrides ]]
    background = string_list( default=list() )
    at now = string_list( default=list() )
    ll_raw = string_list( default=list() )
    ll_basic = string_list( default=list() )
    ll_basic_eco = string_list( default=list() )
    
[ environment ]
__many__ = string

[ tasks ]

    [[ __many__ ]]
    type = option( 'free', 'tied', default='free' )
    # type modifiers: one or more of
    #   'sequential', 'dummy', 'oneoff', 'catchup', 'catchup_contact'
    type modifiers = string_list( default=list() )
    cycles = integer_list( default=list( 0,6,12,18 ))
    commands = string_list( default=list('cylc-wrapper /bin/true'))
    #commands = string_list( default=list() )

    [[[ environment ]]]
    __many__ = string
    

