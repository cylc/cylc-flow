#!/usr/bin/env python


import task
from free import free
from sequential import sequential

#class family( sequential, free ):
class family( free ):

    def run_external_task( self, dry_run=False ):
        self.log( 'DEBUG',  'entering running state' )
        self.incoming( 'NORMAL', self.id + ' started' )

    def satisfy_me( self, task ):
        free.satisfy_me( self, task )
        self.familyfinished_prerequisites.satisfy_me( task )
        #self.familyfailed_prerequisites.satisfy_me( task )
        self.familyOR_prerequisites.satisfy_me( task )

    def check_requisites( self ):
        if not self.state.is_finished():
            if self.familyfinished_prerequisites.all_satisfied():
                self.set_all_internal_outputs_completed()
                self.set_finished()
                task.state_changed = True
        if not self.state.is_failed():
            if self.familyOR_prerequisites.all_satisfied():
                self.outputs.set_all_incomplete()
                #self.incoming( 'NORMAL', self.id + ' failed' )
                self.set_failed('family member(s) failed' )
                task.state_changed = True

    #def XXXXcheck_requisites( self ):
    #    if not self.state.is_finished():
    #        if self.familyfinished_prerequisites.all_satisfied():
    #            if self.state.is_failed():
    #                # suite operator has reset failed family members so
    #                # I need to change state accordingly.
    #                self.log('WARNING', 'Resetting from failed to finished' )
    #                self.prerequisites.set_all_unsatisfied()
    #                self.familyfailed_prerequisites.set_all_unsatisfied()
    #                self.state.set_status('neutral')
    #            self.set_all_internal_outputs_completed()
    #            #self.incoming( 'NORMAL', self.id + ' finished' )
    #            self.set_finished()
    #            task.state_changed = True
    #    if not self.state.is_failed():
    #        if self.familyfailed_prerequisites.all_satisfied():
    #            self.outputs.set_all_incomplete()
    #            #self.incoming( 'NORMAL', self.id + ' failed' )
    #            self.set_failed('family member(s) failed' )
    #            task.state_changed = True

    def not_fully_satisfied( self ):
        if not self.familyfinished_prerequisites.all_satisfied() or \
                free.not_fully_satisfied( self ):
            return True
