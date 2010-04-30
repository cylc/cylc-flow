#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import os
import tempfile
from job_submit import job_submit

class at_now( job_submit ):

    # submit a task using:
    #   at -f FILE now
    # or if a task owner is defined:
    #   sudo -u OWNER at -f FILE now

    # In the latter case /etc/sudoers must be configured to allow the
    # cylc operator to run 'at' as the task owner. FILE is the job
    # submitted to 'at'; it is a temporary file created that sets the
    # execution environment before calling the task script (getting
    # environment variables past 'sudo' and 'at' is otherwise
    # problematic).

    def submit( self ):

        # tempfile.NamedTemporaryFile( delete=False )
        # creates a file and opens it, but delete=False is post python
        # 2.6 and we still currently run 2.4 on some platforms!
        # (auto-delete on close() will remove file before the 'at'
        # command runs it!)

        # tempfile.mktemp() is deprecated in favour of mkstemp()
        # but the latter was also introduced at python 2.6.

        # create a temp file
        temp_filename = tempfile.mktemp( prefix='cylc-') 
        # open the temp file
        temp = open( temp_filename, 'w' )

        # write the execution environment to the temp file
        self.write_local_environment( temp )
        # write the task script execution line to the temp file
        temp.write( self.task )

        temp.close() # (NOTE see NamedTemporaryFile comment above)

        # submit the temp file to 'at' for execution
        if self.owner:
            self.execute_local( 'sudo -u ' + self.owner + ' at -f ' + temp_filename + ' now' )
        else:
            self.execute_local( 'at -f ' + temp_filename + ' now' )
