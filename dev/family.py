#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

# THIS IS THE OBSOLETE PSEUDO-TASK IMPLEMENTATION OF TASK FAMILIES.
# A pseudo-task object is put in the task pool to represent the family.
# The declared family members are made to automatically trigger off it,
# and the family object has extra prerequisites, that it attempts to 
# get satisfied at the same time as its normal prerequisites, used to
# determine its final state based on the states of its members.

class family( object ):
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

    # A "pseudo task" type - families do not submit real external processes.
    is_pseudo_task = True

    def run_external_task( self, dry_run=False ):
        # just report started and enter the 'running' state
        # (only the family members run real tasks).
        self.incoming( 'NORMAL', self.id + ' started' )

    def satisfy_me( self, outputs ):
        self.prerequisites.satisfy_me( outputs )
        #self.suicide_prerequisites.satisfy_me( outputs )
        self.familysucceeded_prerequisites.satisfy_me( outputs )
        self.familyOR_prerequisites.satisfy_me( outputs )

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
        self.state.set_status( 'succeeded' )
        self.prerequisites.set_all_satisfied()
        self.outputs.set_all_completed()
        self.familysucceeded_prerequisites.set_all_satisfied()
        self.familyOR_prerequisites.set_all_unsatisfied()

    def reset_state_failed( self ):
        self.state.set_status( 'failed' )
        self.prerequisites.set_all_satisfied()
        self.outputs.set_all_incomplete()
        self.familysucceeded_prerequisites.set_all_unsatisfied()
        self.familyOR_prerequisites.set_all_satisfied()

    def reset_state_waiting( self ):
        self.state.set_status( 'waiting' )
        self.prerequisites.set_all_unsatisfied()
        self.outputs.set_all_incomplete()
        self.familysucceeded_prerequisites.set_all_unsatisfied()
        self.familyOR_prerequisites.set_all_unsatisfied()

    def reset_state_ready( self ):
        self.state.set_status( 'waiting' )
        self.prerequisites.set_all_satisfied()
        self.outputs.set_all_incomplete()
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
