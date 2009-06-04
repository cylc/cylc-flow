class topnet_vis( parallel_task ):
    "run hourly topnet visualisation off most recent nzlam input" 

    name = "topnet_vis"
    instance_count = 0
    valid_hours = range( 0,24 )
    external_task = 'topnet_vis.sh'
    owner = 'hydrology_oper'
    nzlam_time = None

    def __init__( self, ref_time, initial_state, nzlam_time = None ):

        if nzlam_time:
            topnet_vis.nzlam_time = nzlam_time

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.my_cutoff = self.ref_time

        self.prerequisites = requisites( self.name + '%' + ref_time, [ 
            "topnet finished for " + ref_time ])

        self.postrequisites = timed_requisites( self.name + '%' + ref_time, [ 
            [1, self.name + " started for " + ref_time],
            [3, self.name + " finished for " + ref_time] ])

        parallel_task.__init__( self, initial_state )


    def run_external_task( self, launcher ):
        # topnet needs to be given the time of the netcdf 
        # file that satisified the fuzzy prerequisites

        # extract nzlam time from the nzlam prereq
        topnet_nzlam_time = topnet.nzlam_time

        nzlam_age = 'old'
        if topnet_nzlam_time != topnet_vis.nzlam_time:
            self.log.info( "new nzlam time " + topnet_nzlam_time + ", for " + self.ref_time )
            nzlam_age = 'new'
            topnet_vis.nzlam_time = topnet_nzlam_time
        else:
            self.log.info( "old nzlam time " + topnet_nzlam_time + ", for " + self.ref_time )

        extra_vars = [ ['NZLAM_AGE', nzlam_age ] ]

        parallel_task.run_external_task( self, launcher, extra_vars )


    def dump_state( self, FILE ):
        # topnet_vis needs nzlam_time in the state dump file, otherwise
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
        summary = parallel_task.get_state_summary( self )
        summary[ 'nzlam_time' ] = topnet_vis.nzlam_time
        return summary
