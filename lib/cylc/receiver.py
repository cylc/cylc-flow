#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

import Pyro.core
from cycle_time import ct, CycleTimeError
from copy import deepcopy
import logging

class receiver( Pyro.core.ObjBase ):
    """Receive broadcast variables from cylc clients."""

    def __init__( self ):
        self.targetted = {}  # targetted[ctime][var] = value
        self.universal = {}  # universal[var] = value
        self.log = logging.getLogger('main')
        Pyro.core.ObjBase.__init__(self)
 
    def receive( self, varname, value, target=None, load=False ):
        # currently target validity is checked by client
        if load:
            msg = 'Loaded: '
        else:
            msg = 'Received: '
        msg += varname + '="' + value + '"'
        if not target:
            self.universal[varname] = value
        else:
            msg += ' for ' + target
            if target not in self.targetted:
                self.targetted[target] = {}
            self.targetted[target][varname] = value
        self.log.info( msg )

    def expire( self, expire=None ):
        if not expire:
            # expire all variables immediately
            self.log.warning( 'Expiring all broadcast variables now' ) 
            self.targetted = {}
            self.universal = {}
            return
        newtarg = {}
        for ctime in self.targetted:
            if ctime < expire:
                #print 'RECEIVER: expiring', ctime
                pass
            else:
                newtarg[ctime] = self.targetted[ctime]
        self.targetted = newtarg

    def get( self, taskctime ):
        # retrieve all broadcast variables valid for a given cycle time
        vars = deepcopy( self.universal )
        for ctime in self.targetted:
            if taskctime != ctime:
                continue
            for var, val in self.targetted[ctime].items():
                vars[ var ] = val
        return vars

    def dump( self, FILE ):
        if len( self.universal.items()) > 0:
            FILE.write( 'Begin broadcast variables, universal\n' )
            for var, value in self.universal.items():
                FILE.write( '%s=%s\n' % (var,value) )
            FILE.write( 'End broadcast variables, universal\n' )
        if len( self.targetted.items()) > 0:
            FILE.write( 'Begin broadcast variables, targetted\n' )
            for ctime in self.targetted:
                for var, value in self.targetted[ctime].items():
                    FILE.write( '%s %s=%s\n' % (ctime,var,value) )
            FILE.write( 'End broadcast variables, targetted\n' )

