#!/usr/bin/env python

from free import free
from mod_sequential import sequential

class family( sequential, free ):

    def run_external_task( self, dry_run=False ):
        self.log( 'DEBUG',  'entering running state' )
        self.incoming( 'NORMAL', self.id + ' started' )

    def satisfy_me( self, task ):
        free.satisfy_me( self, task )
        self.familyfinished_prerequisites.satisfy_me( task )

    def check_requisites( self ):
        if self.state.is_finished():
            return
        if self.familyfinished_prerequisites.all_satisfied():
            self.set_all_internal_outputs_completed()
            self.incoming( 'NORMAL', self.id + ' completed' )
            self.incoming( 'NORMAL', self.id + ' finished' )
