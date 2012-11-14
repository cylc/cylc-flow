
[scheduling]
    initial cycle time = integer( default=None )
    final cycle time = integer( default=None )
    cycling = string( default="HoursOfTheDay" ) 
    runahead limit = integer( min=0, default=None )
    [[queues]]
        [[[default]]]
            # for all non queue-assigned tasks
            limit = integer( default=0)
        [[[__many__]]]
            limit = integer( default=0 )
            members = force_list( default=list())
    [[special tasks]]
        clock-triggered = force_list( default=list())
        start-up = force_list( default=list())
        cold-start = force_list( default=list())
        sequential = force_list( default=list())
        one-off = force_list( default=list())
        explicit restart outputs = force_list( default=list())
        exclude at start-up = force_list( default=list())
        include at start-up = force_list( default=list())
    [[dependencies]]
        graph = string( default=None )
        [[[__many__]]]
            graph = string( default=None )
            daemon = string( default=None )

