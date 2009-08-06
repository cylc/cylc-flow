class streamflow( task ):

    name = "streamflow"
    valid_hours = range( 0, 24 )
    external_task = 'streamflow.sh'
    owner = 'hydrology_oper'
    instance_count = 0

    def __init__( self, ref_time, abdicated, initial_state, relative_state = 'catching_up' ):

        if relative_state == 'catching_up':
            streamflow.catchup_mode = True
        else:
            # 'caught_up'
            streamflow.catchup_mode = False
        # Note that streamflow.catchup_mode needs to be written to the
        # state dump file so that we don't need to assume catching up at
        # restart.  Topnet, via its fuzzy prerequisites, can run out to
        # 48 hours ahead of nzlam when caught up, and only 12 hours
        # ahead when catching up.  Therefore if topnet is 18 hours, say,
        # ahead of nzlam when we stop the system, on restart the first
        # topnet to be created will have only a 12 hour fuzzy window,
        # which will cause it to wait for the next nzlam instead of
        # running immediately.

        self.catchup_re = re.compile( "^CATCHINGUP:.*for " + ref_time )
        self.uptodate_re = re.compile( "^CAUGHTUP:.*for " + ref_time )

        # adjust reference time to next valid for this task
        ref_time = self.nearest_ref_time( ref_time )
 
        self.prerequisites = requisites( self.name + '%' + ref_time, [])

        self.postrequisites = timed_requisites( self.name + '%' + ref_time, [
            [0, self.name + " started for " + ref_time],
            [5, "got streamflow data for " + ref_time ],
            [5.1, self.name + " finished for " + ref_time] ])

        task.__init__( self, ref_time, abdicated, initial_state )


    def incoming( self, priority, message ):

        # pass on to the base class message handling function
        task.incoming( self, priority, message)
        
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


    def get_state_string( self ):
        # see comment above on catchup_mode and restarts

        if streamflow.catchup_mode:
            relative_state = 'catching_up'
        else:
            relative_state = 'caught_up'

        return self.state + ':' + relative_state


    def get_state_summary( self ):
        summary = task.get_state_summary( self )
        summary[ 'catching_up' ] = streamflow.catchup_mode
        return summary
