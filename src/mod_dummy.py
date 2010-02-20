#!/usr/bin/python

class dummy:
    # always launch a dummy task, even in real mode
    # TO DO: USE INIT() TO SET EXTERNAL TASK, NOT NECESSARY TO RE-SET IT
    # WITH EVERY CALL TO run_external_task()
    def run_external_task( self, launcher ):
        self.log( 'DEBUG',  'launching external dummy task' )
        self.external_task = '_cylc-dummy-task' 
        launcher.run( self.owner, self.name, self.c_time, self.external_task, self.env_vars )
        self.state.set_status( 'running' )
