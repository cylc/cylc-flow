#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CATCHUP AWARE CONTACT TASK

# Some "advanced" tasks may need different behaviour according to
# whether a contact task that they depende on has "caught up" to real
# time operation or not. 

# This is a contact task that uses a dumpable task class variable to
# record whether or not it has 'caught up' yet.  The class starts off in
# a 'catching up' state, and once 'caught up' stays that way even if
# task instances get behind again (but emits a warning in that case).
# This class state information must be stored in the state dump file so
# that we don't have problems on restart.  E.g. EcoConnect's hourly
# Topnet catchment runs can run out to 48 hours ahead of its NZLAM
# precip input when caught up (in order to make best use of incoming
# real time streamflow observations), but when catching up (e.g.
# starting along way behind real time) it would be counter productive
# for TopNet to get more than the minimum 0-12 hours ahead of NZLAM.
# E.g. if TopNet is say 18 hours ahead of NZLAM when the system is
# stopped, we don't want to assume catching up on restart as that would
# result in a 12 hour fuzzy prerequisites window that would cause TopNet
# to wait on the next NZLAM instead of running immediately.

# HOW TO DETERMINE CATCHUP STATUS: A contact task is still catching up
# if it is ready to run as soon as its prerequisites are satisfied (i.e.
# its delayed start time has already passed at that time). If it has to
# wait for the delayed start time to arrive, then it has caught up.

import re
from mod_contact import contact

class catchup_contact( contact ):

    def __init__( self ):
        # each instance only determines once if it has caught up yet.
        self.catchup_status_determined = False

        # THE ASSOCIATED TASK CLASS MUST DEFINE 
        # self.real_time_delay, for contact:
        contact.__init__( self )

    def ready_to_run( self, current_time ):
        # ready IF waiting AND all prerequisites satisfied AND if my
        # delayed start time is up.
        ready = False
        if self.state.is_waiting() and self.prerequisites.all_satisfied():

            if not self.catchup_status_determined:
                try:
                    caughtup = self.__class__.get_class_var( 'caughtup' )
                    caughtup_rt = self.__class__.get_class_var( 'caughtup_rt' )
                except AttributeError:
                    # this must be the first call after a clean start
                    # so default to 'catching up'
                    self.__class__.set_class_var( 'caughtup', False )
                    self.__class__.set_class_var( 'caughtup_rt', self.c_time )
                    caughtup = True
                    caughtup_rt = self.c_time
                     
            if self.start_time_reached( current_time ):
                # READY TO RUN
                ready = True

                # if this is the first time, delayed start time has
                # passed already, thus we are still catching up.
                if not self.catchup_status_determined:
                    self.catchup_status_determined = True
                    if int( self.c_time ) >= int( caughtup_rt ):
                        self.__class__.set_class_var( 'caughtup', False )
                        self.__class__.set_class_var( 'caughtup_rt', self.c_time )
 
            else:
                # NOT READY, WAITING ON DELAYED START TIME
                ready = False
                self.log( 'DEBUG', 'prerequisites satisfied, but waiting on delayed start time' )

                # if this is the first time, delayed start time has
                # not arrived yet, thus we have caught up.
                if not self.catchup_status_determined:
                    self.catchup_status_determined = True
                    if int( self.c_time ) >= int( caughtup_rt ):
                        self.__class__.set_class_var( 'caughtup', True )
                        self.__class__.set_class_var( 'caughtup_rt', self.c_time )

        return ready
