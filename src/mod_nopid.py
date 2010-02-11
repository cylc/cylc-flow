#!/usr/bin/python

import re

class nopid:
    # NO PREVIOUS INSTANCE DEPENDENCE, FOR NON FORECAST MODELS

    def ready_to_abdicate( self ):
        # Tasks with no previous instance dependence can in principle
        # abdicate as soon as they are created, but this results in
        # waiting tasks out to the maximum runahead, which clutters up
        # monitor views and carries some task processing overhead.
        # Abdicating instead when they start running prevents excess
        # waiting tasks without preventing instances from running in
        # parallel if the opportunity arises. BUT this does mean that a
        # failed or lame task's successor won't exist until the system
        # operator abdicates and kills the offender.

        # Note that tasks with no previous instance dependence and  NO
        # PREREQUISITES will all "go off at once" out to the runahead
        # limit (unless they are contact tasks whose time isn't up yet).
        # These can be constrained with the sequential attribute if that
        # is preferred. 
 
        if self.has_abdicated():
            # already abdicated
            return False

        if self.state.is_finished():
            # always abdicate a finished task
            return True

        if self.state.is_running():
            # see documentation above
            return True


