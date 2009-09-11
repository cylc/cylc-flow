#!/usr/bin/python

from task import task_base
from reference_time import _rt_to_dt
import datetime

# TASK CLASS ATTRIBUTES

# apply to main task classes using multiple inheritance.
# Precedence is left first, e.g.:
#     class foo( oneoff, contact, forecast_model ):
#           pass

class contact:
    # A task that waits on external events such as incoming external
    # data. These are the only tasks that can know if they are are
    # "caught up" or not, according to how their reference time relates
    # to current clock time.

    # The real contact task, once running (which occurs when all of its
    # prerequistes are satisfied), returns only when the external event
    # has occurred. This will be approximately after some known delay
    # relative to the task's reference time (e.g. data arrives 15 min
    # past the hour).  This delay interval needs to be defined for
    # accurate dummy mode simulation.  In catch up operation the
    # external task returns immediately because the external event has
    # already happened (i.e. the required data already exists).

    def __init__( self, relative_state ):

        # catch up status is held as a class variable
        # (i.e. one for each *type* of task proxy object) 
        if relative_state == 'catching_up':
            self.__class__.catchup_mode = True
        else:
            # 'caught_up'
            self.__class__.catchup_mode = False

        # Catchup status needs to be written to the state dump file so
        # that we don't need to assume catching up at restart. 
        # Topnet, via its fuzzy prerequisites, can run out to
        # 48 hours ahead of nzlam when caught up, and only 12 hours
        # ahead when catching up.  Therefore if topnet is 18 hours, say,
        # ahead of nzlam when we stop the system, on restart the first
        # topnet to be created will have only a 12 hour fuzzy window,
        # which will cause it to wait for the next nzlam instead of
        # running immediately.

        # CHILD CLASS MUST DEFINE:
        #   self.real_time_delay
 

    def get_real_time_delay( self ):
        return self.real_time_delay


    def get_state_string( self ):
        # for state dump file
        # see comment above on catchup_mode and restarts

        if self.__class__.catchup_mode:
            relative_state = 'catching_up'
        else:
            relative_state = 'caught_up'

        return self.state + ':' + relative_state


    def get_state_summary( self ):
        # TO DO: FIND A BETTER WAY TO DO THIS... it seems weird to use
        # task_base here in this way, since this attribute class is not
        # derived from task base...
        summary = task_base.get_state_summary( self )
        summary[ 'catching_up' ] = self.__class__.catchup_mode
        return summary


    def run_if_ready( self, launcher, clock ):
        # run if ready *and* the contact delay time is up (there's no
        # point in running earlier as the task will just sit in the
        # queue waiting on the external event).

        if self.state == 'waiting' and self.prerequisites.all_satisfied():

            # check current time against expected start time
            rt = _rt_to_dt( self.ref_time )
            delayed_start = rt + datetime.timedelta( 0,0,0,0,0,self.real_time_delay,0 ) 
            current_time = clock.get_datetime()

            if current_time >= delayed_start:
                # time to run the task

                self.log( 'DEBUG', 'delayed start time has already passed' )
                if self.__class__.catchup_mode:
                    # already catching up
                    pass
                else:
                    # don't reset catchup_mode once catchup has occurred.
                    self.log( 'DEBUG',  'falling behind' )

                # run the external task
                self.run_external_task( launcher )

            else:
                # not yet time to run the task
                
                if self.__class__.catchup_mode:
                    self.log( 'DEBUG',  'just caught up' )
                    self.__class__.catchup_mode = False
                else:
                    # keep waiting 
                    pass

class oneoff:
    # instances of this class always claim they have abdicated already
    def has_abdicated( self ):
        return True

class sequential:
    # instances of this class are not "ready to abdicate" unless they
    # have achieved the 'finished' state.
    def ready_to_abdicate( self ):
        if self.state.has_abdicated():
            return False
        if self.state.is_finished():
            # only abdicate if finished
            return True
        else:
            return False

class dummy:
    # instances of this class always launch a dummy task, even in real mode

    def __init__( self ):
        self.external_task = 'NO_EXTERNAL_TASK'

    def run_external_task( self, launcher ):
        self.log( 'DEBUG',  'launching external dummy task' )
        dummy_out = True
        launcher.run( self.owner, self.name, self.ref_time, self.external_task, dummy_out, self.env_vars )
        self.state = 'running'
