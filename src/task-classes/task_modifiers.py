#!/usr/bin/python

# TASK CLASS MODIFIERS

# These provide new functionality that can be used in a mix-n-match way,
# via multiple inheritance; precedence is left first, task_base on the
# right.

import re
import datetime
from task_base import task_base
from reference_time import _rt_to_dt

class oneoff:
    def ready_to_abdicate( self ):
        self.state.set_abdicated()

    # always claim to have abdicated already
    def has_abdicated( self ):
        return True

class sequential:
    # not "ready to abdicate" unless 'finished'.
    def ready_to_abdicate( self ):
        if self.state.has_abdicated():
            return False
        if self.state.is_finished():
            return True
        else:
            return False

class dummy:
    # always launch a dummy task, even in real mode
    def run_external_task( self, launcher ):
        self.log( 'DEBUG',  'launching external dummy task' )
        dummy_out = True
        launcher.run( self.owner, self.name, self.ref_time, self.external_task, dummy_out, self.env_vars )
        self.state.set_status( 'running' )

class contact:
    # A task that waits on an event in the external world, such as
    # incoming data, that occurs at some known (but approximate) time
    # interval relative to the task reference time.  There's no point in
    # running the task earlier than this delayed start time as the task
    # would just sit in the queue waiting on the external event.

    def __init__( self ):
        # THE ASSOCIATED TASK CLASS MUST DEFINE 
        # self.real_time_delay
        try:
            self.real_time_delay
        except NameError:
            self.log( 'CRITICAL', self.task_name + " requires a real_time_delay" )
            sys.exit(1)

    def get_real_time_delay( self ):
        return self.real_time_delay

    def ready_to_run( self, clock ):
        # ready IF waiting AND all prerequisites satisfied AND if my
        # delayed start time is up.
        ready = False
        if self.state.is_waiting() and self.prerequisites.all_satisfied():
            # check current time against expected start time
            rt = _rt_to_dt( self.ref_time )
            delayed_start = rt + datetime.timedelta( 0,0,0,0,0,self.real_time_delay,0 ) 
            current_time = clock.get_datetime()

            if current_time >= delayed_start:
                ready = True
            else:
                self.log( 'DEBUG', 'ready, but waiting on delayed start time' )

        return ready

class no_previous_instance_dependence:
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

class previous_instance_dependence:
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
