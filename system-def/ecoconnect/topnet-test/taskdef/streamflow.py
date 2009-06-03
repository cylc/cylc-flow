class streamflow( parallel_task ):

    name = "streamflow"
    valid_hours = range( 0, 24 )
    external_task = 'streamflow.sh'
    owner = 'hydrology_oper'
    instance_count = 0

    # assume catchup mode and detect if we've caught up
    catchup_mode = True

    def __init__( self, ref_time, initial_state ):

        self.catchup_re = re.compile( "^CATCHINGUP:.*for " + ref_time )
        self.uptodate_re = re.compile( "^CAUGHTUP:.*for " + ref_time )

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name + '%' + ref_time, [])

        self.postrequisites = timed_requisites( self.name + '%' + ref_time, [
            [0, self.name + " started for " + ref_time],
            [5, "got streamflow data for " + ref_time ],
            [5.1, self.name + " finished for " + ref_time] ])

        parallel_task.__init__( self, initial_state )

    def incoming( self, priority, message ):

        # pass on to the base class message handling function
        parallel_task.incoming( self, priority, message)
        
        # but intercept messages that indicate we're in catchup mode
        if self.catchup_re.match( message ):
            self.log.debug( 'in catching up mode' )
            streamflow.catchup_mode = True

        elif self.uptodate_re.match( message ):
            self.log.debug( 'in caught up mode' )
            streamflow.catchup_mode = False
