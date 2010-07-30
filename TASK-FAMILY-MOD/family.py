#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import task
from free import free
from mod_sequential import sequential

class family( sequential, free ):
    
    def run_external_task( self, dry_run=False ):
        self.log( 'DEBUG',  'entering running state' )
        self.incoming( 'NORMAL', self.id + ' started' )
        task.state_changed = True

    def satisfy_me( self, task ):
        free.satisfy_me( self, task )
        self.familyfinished_prerequisites.satisfy_me( task )

    def check_requisites( self ):
        # set finished if my "finished prerequisites" are all satisfied
        if self.state.is_finished():
            return
        if self.familyfinished_prerequisites.all_satisfied():
            self.set_all_internal_outputs_completed()
            self.incoming( 'NORMAL', self.id + ' completed' )
            self.incoming( 'NORMAL', self.id + ' finished' )
            task.state_changed = True

    def not_fully_satisfied( self ):
        result = False
        if not self.familyfinished_prerequisites.all_satisfied():
            result = True
        if free.not_fully_satisfied( self ):
            result = True
        return result
