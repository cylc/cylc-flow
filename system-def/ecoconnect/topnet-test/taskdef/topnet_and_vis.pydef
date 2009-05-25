class topnet_and_vis( sequential_task ):
    "run hourly topnet and visualisation off most recent nzlam input" 

    name = "topnet_and_vis"
    instance_count = 0
    valid_hours = range( 0,24 )
    external_task = 'topnet_and_vis.sh'
    owner = 'hydrology_oper'
    nzlam_time = None

    # cutoff in hours (min wait before killing upstream tasks)
    CATCHUP_MODE_CUTOFF  = 11
    CAUGHTUP_MODE_CUTOFF = 23   

    fuzzy_file_re =  re.compile( "^file (tn_\d{10}_utc_nzlam_12.nc) ready$" )
    reftime_re = re.compile( "\d{10}")

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        if streamflow.catchup_mode:
            self.my_cutoff = reference_time.decrement( ref_time, topnet_and_vis.CATCHUP_MODE_CUTOFF )
        else:
            self.my_cutoff = reference_time.decrement( ref_time, topnet_and_vis.CAUGHTUP_MODE_CUTOFF )

        # min:max
        fuzzy_limits = self.my_cutoff + ':' + ref_time
 
        self.prerequisites = fuzzy_requisites( self.name + '%' + ref_time, [ 
            "got streamflow data for " + ref_time + ':' + ref_time, 
            "file tn_" + fuzzy_limits + "_utc_nzlam_12.nc ready" ])

        self.postrequisites = timed_requisites( self.name + '%' + ref_time, [ 
            [3, self.name + " started for " + ref_time],
            [3.1, "topnet started for " + ref_time],
            [6,   "topnet finished for " + ref_time],
            [6.1, "topnet vis started for " + ref_time ],
            [8.9, "topnet vis finished for " + ref_time ],
            [9, self.name + " finished for " + ref_time] ])

        sequential_task.__init__( self, ref_time, initial_state )

        self.log.debug( "nzlam cutoff is " + self.my_cutoff + " for " + ref_time )


    def run_external_task( self, launcher ):
        # topnet needs to be given the time of the netcdf 
        # file that satisified the fuzzy prerequisites

        # extract nzlam time from the nzlam prereq
        nzlam_time = None
        prereqs = self.prerequisites.get_list()
        for prereq in prereqs:
            m = topnet_and_vis.fuzzy_file_re.match( prereq )
            if m:
                # found the nzlam prereq
                [ file ] = m.groups()
                m = topnet_and_vis.reftime_re.search( file )
                nzlam_time = m.group()
                break
 
        if not nzlam_time:
            print "ERROR: failed to find nzlam time"
            sys.exit(1)

        nzlam_age = 'old'
        if nzlam_time != topnet_and_vis.nzlam_time:
            # NEW NZLAM INPUT DETECTED
            # when a new topnet is launched, determine if its
            # prerequisites were satisfied by a new nzlam
            self.log.info( "new nzlam time detected:  " + nzlam_time )
            nzlam_age = 'new'
            topnet_and_vis.nzlam_time = nzlam_time

        extra_vars = [ 
                ['NZLAM_TIME', nzlam_time ],
                ['NZLAM_AGE', nzlam_age ] ]
        sequential_task.run_external_task( self, launcher, extra_vars )


    def get_cutoff( self ):

        # must keep the most recent *finished* nzlam_06_18_post or
        # oper2test_topnet task that is older than me, because the next
        # hourly topnet may also need the output from that same
        # 12-hourly task.

        return self.my_cutoff
