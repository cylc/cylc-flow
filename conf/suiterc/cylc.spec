[cylc]
    UTC mode = boolean( default=False )
    required run mode = option( 'live','dummy','simulation', default=None )
    pyro connection timeout = float( min=0.0, default=None )
    maximum simultaneous job submissions = integer( min=1, default=50 )
    abort if any task fails = boolean( default=False )
    log resolved dependencies = boolean( default=False )
    [[lockserver]]
        enable = boolean( default=False )
        simultaneous instances = boolean( default=False )
    [[environment]]
        __many__ = string
    [[event hooks]]
        startup handler = string( default=None )
        timeout handler = string( default=None )
        shutdown handler = string( default=None ) 
        timeout = float( default=None )
        reset timer = boolean( default=True )
        abort if startup handler fails = boolean( default=False )
        abort if shutdown handler fails = boolean( default=False )
        abort if timeout handler fails = boolean( default=False )
        abort on timeout = boolean( default=False )
    [[simulation mode]]
        disable suite event hooks = boolean( default=True )
    [[dummy mode]]
        disable suite event hooks = boolean( default=True )
    [[accelerated clock]]
        disable = boolean( default=False )
        rate = integer( default=10 )
        offset = integer( default=24 )
    [[reference test]]
        suite shutdown event handler = string( default='cylc hook check-triggering' )
        required run mode = option( 'live', 'simulation', 'dummy', default=None )
        allow task failures = boolean( default=False )
        expected task failures = force_list( default=list() )
        live mode suite timeout = float( default=None )
        dummy mode suite timeout = float( default=None )
        simulation mode suite timeout = float( default=None )

