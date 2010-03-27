#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import re

class pid:
    # PREVIOUS INSTANCE DEPENDENCE FOR FORECAST MODELS

    # Forecast models depend on a previous instance via their restart
    # files. This class provides a method to register special restart
    # prerequisites and outputs, and overrides
    # free_task.ready_to_spawn() appropriately.
    
    def register_restarts( self, output_times ):
        # call after parent init, so that self.c_time is defined!

        msg = self.name + ' restart files ready for '
        self.prerequisites.add(  msg + self.c_time )

        rt = self.c_time
        for t in output_times:
            next_rt = self.next_c_time( rt )
            self.outputs.add( t, msg + next_rt )
            rt = next_rt

    def set_next_restart_completed( self ):
        restart_messages = []
        for message in self.outputs.satisfied.keys():
            if re.search( 'restart files ready for', message ):
                restart_messages.append( message )

        restart_messages.sort()
        for message in restart_messages:
            if not self.outputs.is_satisfied( message ):
                self.log( 'NORMAL', message )
                self.latest_message = message
                self.outputs.set_satisfied( message )


    def set_all_restarts_completed( self ):
        # convenience for external tasks that don't report restart
        # outputs one at a time.
        self.log( 'WARNING', 'setting ALL restart outputs completed' )
        for message in self.outputs.satisfied.keys():
            if re.search( 'restart files ready for', message ):
                self.outputs.set_satisfied( message )
                self.latest_message = message
 

    def ready_to_spawn( self ):
        # Never spawn a waiting task of this type because the
        # successor's restart prerequisites could get satisfied by the
        # later restart outputs of an earlier previous instance, and
        # thereby start too soon (we want this to happen ONLY if the
        # previous task fails and is subsequently made to spawn and 
        # die by the system operator).

        if self.has_spawned():
            # already spawned
            return False

        if self.state.is_waiting() or self.state.is_submitted():
            return False

        if self.state.is_finished():
            # always spawn a finished task
            return True

        ready = False

        if self.state.is_running() or self.state.is_failed(): 
            # failed tasks are running before they fail, so will already
            # have spawned, or not, according to whether they fail
            # before or after completing their restart outputs.

            # ready only if all restart outputs are completed
            # as explained above

            ready = True
            for message in self.outputs.satisfied.keys():
                if re.search( 'restart files ready for', message ) and \
                        not self.outputs.satisfied[ message ]:
                    ready = False
                    break

        return ready
