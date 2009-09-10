#!/usr/bin/python

import re
from task import task_base

# MAIN TASK CLASS FOR NON FORECAST MODEL TASKS

class general_purpose( task_base ):

    # Tasks with no previous instance dependence can in principle
    # abdicate immediately, but this creates waiting tasks out to the
    # max runahead, which clutters up monitor views and carries some
    # task processing overhead.
            
    # Waiting until they are running prevents excess waiting tasks
    # without preventing instances from running in parallel if the
    # opportunity arises.
            
    # BUT this does mean that a failed or lame task's successor won't
    # exist until the system operator abdicates and kills the offender.

    # Note that tasks with no previous instance dependence and  NO
    # PREREQUISITES will all "go off at once" out to the runahead 
    # limit (unless they are contact tasks whose time isn't up yet). 
    # These can be constrained with the sequential attribute if
    # that is preferred. 
 
    def ready_to_abdicate( self ):

        if self.has_abdicated():
            # already abdicated
            return False

        if self.state == 'finished':
            # always abdicate a finished task
            return True

        if self.state == 'running':
            # see documentation above
            return True
