#!/usr/bin/python

class dummy:
    # always launch a dummy task, even in real mode
    def run_external_task( self, launcher ):
        self.log( 'DEBUG',  'launching external dummy task' )
        dummy_out = True
        launcher.run( self.owner, self.name, self.c_time, self.external_task, dummy_out, self.env_vars )
        self.state.set_status( 'running' )
