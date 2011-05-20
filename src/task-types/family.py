#!/usr/bin/env python


import task
from free import free
from sequential import sequential

class family( free ):
    """
Task family implementation in cylc: a task that just enters the running
state when ready, without running anything for real, so that it's members
can trigger off it.  Also it has two special prerequisite types: 
    1/ "family succeeded prerequisites" - these express dependence on all
    family members finishing successfully.
    2/ "family OR prerequisites" - conditional prerequisites that express
    dependence on (member1 succeeded OR failed) AND (member2 succeeded OR failed) AND ...
    If these are all satisfied it means that all members have either succeeded 
    or failed. They cannot be all satisfied while any task is
    yet to finish or fail.
Thus, we can tell by 1/ if ALL members succeeded => family succeeded;
and by 2/, if ALL members have either succeeded OR failed, i.e. no members 
are still waiting, submitted, or running. if 1/ is not all satisifed but two is => at
least one member failed => the family failed.  Downstream tasks can thus trigger off
a family finishing or failing, with no danger of triggering before some members may
still finish successfully, as could happen if the family entered the 'failed' state 
as soon as any one member failed.
    """

    def run_external_task( self, dry_run=False ):
        # just report started and enter the 'running' state
        # (only the family members run real tasks).
        self.incoming( 'NORMAL', self.id + ' started' )

    def satisfy_me( self, task ):
        free.satisfy_me( self, task )
        self.familysucceeded_prerequisites.satisfy_me( task )
        self.familyOR_prerequisites.satisfy_me( task )

    def check_requisites( self ):
        if self.familysucceeded_prerequisites.all_satisfied():
            # all members completed successfully
            self.set_all_internal_outputs_completed()
            self.incoming( 'NORMAL', 'all family members succeeded' )
            self.incoming( 'NORMAL', self.id + ' succeeded' )
            #self.set_succeeded()
            #task.state_changed = True
        elif self.familyOR_prerequisites.all_satisfied():
            # all members completed successfully OR failed
            # so the 'elif' => one or more members failed.
            self.outputs.set_all_incomplete()
            #self.set_failed('family member(s) failed' )
            self.incoming( 'CRITICAL', 'family member(s) failed' )
            self.incoming( 'CRITICAL', self.id + ' failed' )

    def reset_state_succeeded( self ):
        free.reset_state_succeeded( self )
        self.familysucceeded_prerequisites.set_all_satisfied()
        self.familyOR_prerequisites.set_all_unsatisfied()

    def reset_state_failed( self ):
        free.reset_state_failed( self )
        self.familysucceeded_prerequisites.set_all_unsatisfied()
        self.familyOR_prerequisites.set_all_satisfied()

    def reset_state_waiting( self ):
        free.reset_state_waiting( self )
        self.familysucceeded_prerequisites.set_all_unsatisfied()
        self.familyOR_prerequisites.set_all_unsatisfied()

    def reset_state_ready( self ):
        free.reset_state_ready( self )
        self.familysucceeded_prerequisites.set_all_unsatisfied()
        self.familyOR_prerequisites.set_all_unsatisfied()

    def not_fully_satisfied( self ):
        # keep negotiating until all family members have succeeded or failed.
        if self.familysucceeded_prerequisites.all_satisfied() or \
            self.familyOR_prerequisites.all_satisfied():
            # we are fully satisfied
            return False
        else:
            # we're not
            return True
