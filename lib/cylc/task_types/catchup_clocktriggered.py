#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

# A catchup-aware clock-triggered task.

# For (rare!) tasks that need different behaviour according to whether
# a clock-triggered task that they depend on has caught up to real
# time operation or not. 

# This is a clock-triggered task that uses a dumpable task class
# variable to
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
# E.g. if TopNet is say 18 hours ahead of NZLAM when the suite is
# stopped, we don't want to assume catching up on restart as that would
# result in a 12 hour fuzzy prerequisites window that would cause TopNet
# to wait on the next NZLAM instead of running immediately.

# HOW TO DETERMINE CATCHUP STATUS: A clock-triggered task is still
# catching up if it is ready to run as soon as its prerequisites are
# satisfied (i.e. its delayed start time has already passed at that
# time). If it has to wait for the delayed start time to arrive then it
# has caught up already.

# DEV NOTE: THIS CLASS HAS NOT BEEN USED SINCE CYLC-2; IT MAY NEED UPDATING.

import re
from clocktriggered import clocktriggered

class catchup_clocktriggered( clocktriggered ):

    def __init__( self ):
        # each instance only determines once if it has caught up yet.
        self.catchup_status_determined = False

        # THE ASSOCIATED TASK CLASS MUST DEFINE 
        # self.real_time_delay, for clocktriggered:
        clocktriggered.__init__( self )

    def ready_to_run( self ):
        # ready IF waiting AND all prerequisites satisfied AND if my
        # delayed start time is up.
        ready = False
        if self.state.is_currently('queued') or \
                self.state.is_currently('waiting') and self.prerequisites.all_satisfied() or \
                 self.state.is_currently('retrying') and self.prerequisites.all_satisfied():

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
                     
            if self.start_time_reached():
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
