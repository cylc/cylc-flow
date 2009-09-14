#!/usr/bin/python

# CATCHUP AWARE FREE CONTACT TASK

# Some "advanced" tasks may need different behaviour according to
# whether a contact task that they depende on has "caught up" to real
# time operation or not. 

# This is a contact task with some additional features. It requires
# new information in the state dump file, so we have to derive from
# task_base and override the init method.

# E.g. EcoConnect's hourly Topnet catchment runs can run out to 48 hours
# ahead of its NZLAM precip input when caught up (in order to make best
# use of incoming real time streamflow observations), but when catching
# up (e.g. starting along way behind real time) it would be counter
# productive for TopNet to get more than the minimum 0-12 hours ahead of
# NZLAM. 

# Catchup status must be stored in the state dump file, so that we don't
# have problems on restart.  E.g. if TopNet is say 18 hours ahead of
# NZLAM when the system is stopped, we don't want to assume catching up
# on restart as that would result in a 12 hour fuzzy prerequisites
# window that would cause TopNet to wait on the next NZLAM instead of
# running immediately.

# HOW TO DETERMINE CATCHUP STATUS: A contact task is still catching up
# if it is ready to run as soon as its prerequisites are satisfied (i.e.
# its delayed start time has already passed at that time). If it has to
# wait for the delayed start time to arrive, then it has caught up.

import re
import datetime
from task_modifiers import contact
from task_types import free_task
from reference_time import _rt_to_dt

class catchup_aware_free_task( contact, free_task ):

    def __init__( self, state_dump_string = None ):
        # on restart from state dump, the special state variable 
        # will already exist. 
        self.catchup_status_determined = False
        if state_dump_string:
            if re.search( 'caught_up', state_dump_string ):
                self.catchup_status_determined = True

        contact.__init__( self )
        free_task.__init__( self, state_dump_string )


    def get_state_summary( self ):
        summary = free_task.get_state_summary( self )
        if self.state.has_key( 'caught_up'):
            caught_up = False
            if self.state.get( 'caught_up' ) == 'true':
                caught_up = True
            summary[ 'catching_up' ] = not caught_up
        return summary

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
                # READY TO RUN
                ready = True
                # check catchup status the first time
                if not self.catchup_status_determined:
                    self.state.set( 'caught_up', 'false' )
                    self.catchup_status_determined = True

            else:
                # NOT READY, WAITING ON DELAYED START TIME
                # check catchup status the first time
                self.log( 'DEBUG', 'ready, but waiting on delayed start time' )
                if not self.catchup_status_determined:
                    self.state.set( 'caught_up', 'true' )
                    self.catchup_status_determined = True

        return ready
