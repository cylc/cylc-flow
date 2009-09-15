#!/usr/bin/python

import re

class pid:
    # PREVIOUS INSTANCE DEPENDENCE FOR FORECAST MODELS

    # Forecast models depend on a previous instance via their restart
    # files. This class provides a method to register special restart
    # prerequisites and outputs, and overrides
    # free_task.ready_to_abdicate() appropriately.
    
    def register_restarts( self, output_times ):
        # call after parent init, so that self.ref_time is defined!

        msg = self.name + ' restart files ready for '
        self.prerequisites.add(  msg + self.ref_time )

        rt = self.ref_time
        for t in output_times:
            next_rt = self.next_ref_time( rt )
            self.outputs.add( t, msg + next_rt )
            rt = next_rt

    def ready_to_abdicate( self ):
        # Never abdicate a waiting task of this type because the
        # successor's restart prerequisites could get satisfied by the
        # later restart outputs of an earlier previous instance, and
        # thereby start too soon (we want this to happen ONLY if the
        # previous task fails and is subsequently abdicated-and-killed
        # by the system operator).

        if self.has_abdicated():
            # already abdicated
            return False

        if self.state.is_finished():
            # always abdicate a finished task
            return True

        ready = False

        if self.state.is_running() or self.state.is_failed(): 
            # failed tasks are running before they fail, so will already
            # have abdicated, or not, according to whether they fail
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
