#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import re

class nopid(object):
    # NO PREVIOUS INSTANCE DEPENDENCE, FOR NON FORECAST MODELS

    def ready_to_spawn( self ):
        # Tasks with no previous instance dependence can in principle
        # spawn as soon as they are created, but this results in
        # waiting tasks out to the maximum runahead, which clutters up
        # monitor views and carries some task processing overhead.
        # Abdicating instead when they start running prevents excess
        # waiting tasks without preventing instances from running in
        # parallel if the opportunity arises. BUT this does mean that a
        # failed or lame task's successor won't exist until the suite
        # operator gets the offender to spawn and die.

        # Note that tasks with no previous instance dependence and  NO
        # PREREQUISITES will all "go off at once" out to the runahead
        # limit (unless they are contact tasks whose time isn't up yet).
        # These can be constrained with the sequential attribute if that
        # is preferred. 
 
        if self.has_spawned():
            # already spawned
            return False

        if self.state.is_running() or self.state.is_finished():
            # see documentation above
            return True
        else:
            return False
