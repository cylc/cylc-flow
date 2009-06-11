class topnet( task ):
    "run hourly topnet off the most recent nzlam input" 

    name = "topnet"
    instance_count = 0
    valid_hours = range( 0,24 )
    external_task = 'topnet.sh'
    owner = 'hydrology_oper'
    nzlam_time = None

    # for fuzzy prerequiste satisfaction limits
    CATCHUP_MODE_CUTOFF  = 11
    CAUGHTUP_MODE_CUTOFF = 47   

    fuzzy_file_re =  re.compile( "^file (tn_\d{10}_utc_nzlam_12.nc) ready$" )
    reftime_re = re.compile( "\d{10}")

    def __init__( self, ref_time, initial_state, nzlam_time = None ):

        if nzlam_time:
            topnet.nzlam_time = nzlam_time

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        if streamflow.catchup_mode:
            cutoff = reference_time.decrement( self.ref_time, topnet.CATCHUP_MODE_CUTOFF )
        else:
            cutoff = reference_time.decrement( self.ref_time, topnet.CAUGHTUP_MODE_CUTOFF )

        fuzzy_limits = cutoff + ':' + ref_time
 
        self.prerequisites = fuzzy_requisites( self.name + '%' + ref_time, [ 
            "got streamflow data for " + ref_time + ':' + ref_time, 
            "file tn_" + fuzzy_limits + "_utc_nzlam_12.nc ready" ])

        self.postrequisites = timed_requisites( self.name + '%' + ref_time, [ 
            [1,  self.name + " started for " + ref_time],
            [10, self.name + " finished for " + ref_time] ])

        task.__init__( self, initial_state )


    def run_external_task( self, launcher ):

        # At task run time, let's see if new nzlam output is available.
        # Topnet needs to be given the time of the netcdf file that
        # satisified its (fuzzy) prerequisites

        # extract nzlam time from the nzlam prereq
        nzlam_time = None
        prereqs = self.prerequisites.get_list()
        for prereq in prereqs:
            m = topnet.fuzzy_file_re.match( prereq )
            if m:
                # found the nzlam prereq
                [ file ] = m.groups()
                m = topnet.reftime_re.search( file )
                nzlam_time = m.group()
                break
 
        if not nzlam_time:
            raise( "Failed to find nzlam time, for " + self.ref_time )

        if nzlam_time != topnet.nzlam_time:
            # NEW NZLAM INPUT DETECTED
            # when a new topnet is launched, determine if its
            # prerequisites were satisfied by a new nzlam
            self.log.info( "new nzlam time " + nzlam_time + ', for ' + self.ref_time )
            topnet.nzlam_time = nzlam_time
        else:
            self.log.info( "old nzlam time " + nzlam_time + ', for ' + self.ref_time )

        extra_vars = [ ['NZLAM_TIME', nzlam_time ] ]

        task.run_external_task( self, launcher, extra_vars )


    def get_cutoff( self, finished_task_dict ):
        # See base class documentation

        # the task manager must keep the most recent *finished*
        # nzlam_06_18_post or oper_interface task that is older than me,
        # because the next hourly topnet may also need the output from
        # that same 12-hourly task.

        if self.state == 'waiting' or \
            ( self.state == 'running' and not self.abdicated ) or \
            ( self.state == 'finished' and not self.abdicated ):

            cutoff = self.ref_time

            ref_times = []
            if 'oper_interface' in finished_task_dict.keys():
                ref_times = finished_task_dict[ 'oper_interface' ]

            elif 'nzlam_06_18_post' in finished_task_dict.keys():
                ref_times = finished_task_dict[ 'nzlam_06_18_post' ]

            ref_times.sort( key = int, reverse = True )
            for rt in ref_times:
                if int( rt ) <= int( self.ref_time ):
                    cutoff = rt
                    break
        else:
            cutoff = None

        return cutoff


    def dump_state( self, FILE ):
        # topnet needs nzlam_time in the state dump file, otherwise
        # it will always assume new nzlam input at restart time.

        if topnet.nzlam_time:
            state_string = self.state + ':' + topnet.nzlam_time
        else:
            state_string = self.state

        FILE.write( 
                self.ref_time + ' ' + 
                self.name     + ' ' + 
                state_string + '\n' )


    def get_state_summary( self ):
        summary = task.get_state_summary( self )
        summary[ 'nzlam_time' ] = topnet.nzlam_time
        return summary
