#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import os, re
import tempfile
from job_submit import job_submit

class loadleveler_ecoconnect( job_submit ):

    # llsubmit an EcoConnect task to run as its owner
    #   sudo -u OWNER llsubmit FILE 

    # /etc/sudoers must be configured to allow the cylc operator 
    # (ecoconnect_devel, ecoconnect_test, ecoconnect_oper) to run
    # llsubmit as task owner ({foo}_devel, {foo}_test, {foo}_oper).
    # FILE is a temporary file created to contain loadleveler
    # directives and set the execution environment before running
    # the task (getting environment variables past 'sudo' and 
    # llsubmit is otherwise problematic).

    def submit( self ):

        # tempfile.NamedTemporaryFile( delete=False )
        # creates a file and opens it, but delete=False is post python
        # 2.6 and we still currently run 2.4 on some platforms!
        # (auto-delete on close() will remove file before the 'at'
        # command runs it!)

        # tempfile.mktemp() is deprecated in favour of mkstemp()
        # but the latter was also introduced at python 2.6.

        # which system are we running on (devel, test, oper)?
        cylc_user = os.environ['USER']
        cylc_home = os.environ['HOME']
        system = re.sub( '^.*_', '', cylc_user )  

        # adjust task owner for the system
        if not self.owner:
            raise SystemExit( "No owner for EcoConnect task " + self.task_name )

        owner = self.owner
        if re.match( '^.*_oper', owner ):
            # strip off the system suffix
            owner = re.sub( '_oper$', '', owner )

        # append the correct system suffix
        owner += '_' + system

        # create a temp file
        jobfilename = tempfile.mktemp( prefix='cylc-') 
        # open the temp file
        jobfile = open( jobfilename, 'w' )

        # write loadleveler directives
        jobfile.write( "#@ job_name     = " + self.task_name + "_" + self.cycle_time + "\n" )
        #jobfile.write( "#@ class        = " + system + "\n" )     # WHEN PROPER CLASSES CONFIGURED!
        jobfile.write( "#@ class        = test_linux \n" )  # TEMPORARY fc-test ONLY CLASS
        jobfile.write( "#@ job_type     = serial\n" )
        jobfile.write( "#@ initialdir  = /" + system + "/ecoconnect/" + owner + "\n" )
        jobfile.write( "#@ output       = " + self.task_name + "_" + self.cycle_time + ".out\n" )
        jobfile.write( "#@ error        = " + self.task_name + "_" + self.cycle_time + ".err\n" )
        jobfile.write( "#@ shell        = /bin/bash\n" )
        jobfile.write( "#@ queue\n\n" )

        self.write_job_env( jobfile )
        jobfile.write( ". " + cylc_home + "/bin/ecfunctions.sh\n\n" )
        jobfile.write( self.task )
        jobfile.close() 

        self.execute( 'llsubmit ' + jobfilename )
