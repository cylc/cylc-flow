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
        temp_filename = tempfile.mktemp( prefix='cylc-') 
        # open the temp file
        temp = open( temp_filename, 'w' )

        # write loadleveler directives
        temp.write( "#@ job_name     = " + self.task_name + "_" + self.cycle_time + "\n" )
        #temp.write( "#@ class        = " + system + "\n" )     # WHEN PROPER CLASSES CONFIGURED!
        temp.write( "#@ class        = test_linux \n" )  # TEMPORARY fc-test ONLY CLASS
        temp.write( "#@ job_type     = serial\n" )
        temp.write( "#@ initialdir  = /" + system + "/ecoconnect/" + owner + "\n" )
        temp.write( "#@ output       = " + self.task_name + "_" + self.cycle_time + ".out\n" )
        temp.write( "#@ error        = " + self.task_name + "_" + self.cycle_time + ".err\n" )
        temp.write( "#@ shell        = /bin/bash\n" )
        temp.write( "#@ queue\n\n" )

        # write the execution environment to the temp file
        self.write_local_environment( temp )
        temp.write( ". " + cylc_home + "/bin/ecfunctions.sh\n" )

        # write the task script execution line to the temp file
        temp.write( self.task )

        # close the file
        temp.close() # (NOTE see NamedTemporaryFile comment above)

        # submit the temp file to 'at' for execution
        self.execute_local( 'sudo -u ' + owner + ' llsubmit ' + temp_filename )
