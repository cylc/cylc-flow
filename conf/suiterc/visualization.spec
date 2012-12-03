[visualization]
    initial cycle time = integer( default=None )
    final cycle time = integer( default=None )
    collapsed families = force_list( default=list() )
    use node color for edges = boolean( default=True )
    use node color for labels = boolean( default=False )
    default node attributes = force_list( default=list('style=unfilled', 'color=black', 'shape=box'))
    default edge attributes = force_list( default=list('color=black'))
    enable live graph movie = boolean( default=False )
    [[node groups]]
        __many__ = force_list( default=list())
    [[node attributes]]
        __many__ = force_list( default=list())
    [[runtime graph]]
        enable = boolean( default=False )
        cutoff = integer( default=24 )
        directory = string( default='$CYLC_SUITE_DEF_PATH/graphing')

