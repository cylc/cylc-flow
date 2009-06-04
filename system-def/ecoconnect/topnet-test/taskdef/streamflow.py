class streamflow( parallel_task ):

    name = "streamflow"
    valid_hours = range( 0, 24 )
    external_task = 'streamflow.sh'
    owner = 'hydrology_oper'
    instance_count = 0

    # start in catchup mode and detect if we've caught up
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
        
        # but intercept messages to do with catchup mode
        if self.catchup_re.match( message ):
            # message says we're catching up to real time
            if not self.catchup_mode:
                # We were caught up and have apparently slipped back a
                # bit. Do NOT revert to catching up mode because this
                # will suddenly reduce topnet's cutoff time
                # and may result in deletion of a finished nzlam task
                # that is still needed to satsify topnet prerequisites
                self.log.debug( 'falling behind the pace a bit here' )
            else:
                # We were already catching up; no change.
                pass

        elif self.uptodate_re.match( message ):
            # message says we've caught up to real time
            if not self.catchup_mode:
                # were already caught up; no change
                pass
            else:
                # we have just caught up
                self.log.debug( 'just caught up to real time' )
                streamflow.catchup_mode = False
