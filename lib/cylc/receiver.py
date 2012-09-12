#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
from cylc.TaskID import TaskID, InvalidTaskIDError, InvalidCycleTimeError

class receiver( Pyro.core.ObjBase ):
    """Receive broadcast variables from cylc clients."""

    def __init__( self ):
        self.universal = {}           # universal[var] = value
        self.targetted = {}
        self.targetted['id'] = {}     # targetted['id'][id][var] = value
        self.targetted['name'] = {}   # targetted['name'][name][var] = value
        self.targetted['tag'] = {}    # targetted['tag'][tag][var] = value
        self.log = logging.getLogger('main')
        Pyro.core.ObjBase.__init__(self)
 
    def receive( self, varname, value, target=None, load=False ):
        result = ( True, 'OK' )
        # currently target validity is checked by client
        if load:
            msg = 'Loaded: '
        else:
            msg = 'Received: '
        msg += varname + '="' + value + '"'
        if not target:
            # no target: universal broadcast
            self.universal[varname] = value
        else:
            msg += ' for ' + target
            self.log.info( msg )
            try:
                # is it a task ID?
                tid = TaskID( target )
            except InvalidTaskIDError:
                try:
                    # is it a task tag (cycle time or int)
                    tid = TaskID( 'junk%' + target )
                except InvalidTaskIDError:
                    try:
                        # is it a task name?
                        tid = TaskID( target + '%1' )
                    except InvalidTaskIDError:
                        # don't let a bad broadcast bring the suite down!
                        self.log.warning( 'Broadcast error, invalid target: ' + target )
                        result = ( False, 'Invalid target: ' + target )
                    else:
                        # target any task with this name
                        if target not in self.targetted['name']:
                            self.targetted['name'][target] = {}
                        self.targetted['name'][target][varname] = value
                else:
                    # target any task with this tag
                    if target not in self.targetted['tag']:
                        self.targetted['tag'][target] = {}
                    self.targetted['tag'][target][varname] = value
            else:
                # target a specific task
                if target not in self.targetted['id']:
                    self.targetted['id'][target] = {}
                self.targetted['id'][target][varname] = value

        return result

    def expire( self, expire=None ):
        if not expire:
            # expire all variables immediately
            self.log.warning( 'Expiring all broadcast variables now' ) 
            self.universal = {}
            self.targetted['id'] = {}
            self.targetted['name'] = {}
            self.targetted['tag'] = {}
            return

        newtarg = {}
        for ctime, val in self.targetted['tag'].items():
            if ctime < expire:
                print 'RECEIVER: expiring', ctime
                pass
            else:
                newtarg[ctime] = val
        self.targetted['tag'] = newtarg

        newtarg = {}
        for id, val in self.targetted['id'].items():
            name, ctime = id.split('%')
            if ctime < expire:
                print 'RECEIVER: expiring', id
                pass
            else:
                newtarg[id] = val
        self.targetted['id'] = newtarg

    def get( self, id ):
        # Retrieve all broadcast variables that can target a given task ID.
        name, tag = id.split('%')

        # first take the universal variables:
        vars = deepcopy( self.universal )

        # then add in cycle-specific variables:
        for i_tag in self.targetted['tag']:
            if tag != i_tag:
                continue
            for var, val in self.targetted['tag'][i_tag].items():
                vars[ var ] = val

        # then task-name-specific variables:
        for i_name in self.targetted['name']:
            if i_name != name:
                continue
            for var, val in self.targetted['name'][i_name].items():
                vars[ var ] = val

        # then task-specific variables:
        for i_id in self.targetted['id']:
            if i_id != id:
                continue
            for var, val in self.targetted['id'][i_id].items():
                vars[ var ] = val

        return vars

    def dump( self, FILE ):
        # write broadcast variables to the suite state dump file
        if len( self.universal.items()) > 0:
            FILE.write( 'Begin broadcast variables, universal\n' )
            for var, value in self.universal.items():
                FILE.write( '%s=%s\n' % (var,value) )
            FILE.write( 'End broadcast variables, universal\n' )
        for ttype in [ 'id', 'name', 'tag' ]:
            if len( self.targetted[ttype].items() ) > 0:
                FILE.write( 'Begin broadcast variables, targetted by ' + ttype + '\n' )
                for item in self.targetted[ttype]:
                    for var, value in self.targetted[ttype][item].items():
                        FILE.write( '%s %s=%s\n' % (item,var,value) )
                FILE.write( 'End broadcast variables, targetted by ' + ttype + '\n' )

