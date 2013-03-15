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

import Pyro.core
from cycle_time import ct, CycleTimeError
from copy import deepcopy
from datetime import datetime
import logging, os, sys
import cPickle as pickle
from cylc.TaskID import TaskID, InvalidTaskIDError, InvalidCycleTimeError
from configobj import ConfigObj, ConfigObjError, get_extra_values, flatten_errors, Section
from rundb import RecordBroadcastObject
from validate import Validator

class broadcast( Pyro.core.ObjBase ):
    """Receive broadcast variables from cylc clients."""

    # examples:
    #self.settings[ 'all' ][ 'root' ] = "{ 'environment' : { 'FOO' : 'bar' }}
    #self.settings[ '2010080806' ][ 'root' ] = "{ 'command scripting' : 'stuff' }

    def __init__( self, linearized_ancestors ):
        self.log = logging.getLogger('main')
        self.settings = {}
        self.last_settings = self.get_dump()
        self.new_settings = False
        self.settings_queue = []
        self.linearized_ancestors = linearized_ancestors
        self.spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suiterc', 'runtime.spec')
        Pyro.core.ObjBase.__init__(self)

    def validate( self, settings ):
        # validate new broadcast settings against the suite.rc spec file
        try:
            cfg = ConfigObj( infile=settings, configspec=self.spec )
        except ConfigObjError, x:
            print >> sys.stderr, x # shouldn't happen
            return ( False, 'ERROR: failed to load new broadcast settings' )

        val = Validator()
        test = cfg.validate( val, preserve_errors=False )
        if test != True:
            msg = "Broadcast validation failed:"
            failed_items = flatten_errors( cfg, test )
            # Always print reason for validation failure
            for item in failed_items:
                sections, key, result = item
                msg += ' '
                for sec in sections:
                    msg += sec + ' / '
                msg += key
                if result == False:
                    msg += "\n required item missing."
                else:
                    msg += "\n " + str( result )
            ### return ( False, msg )
            ### We do not currently have any required suite.rc items
            # (i.e. items with no defaults supplied) but even if we did
            # this would not be an error for broadcasting purposes.

        extras = []
        for sections, name in get_extra_values( cfg ):
            extra = ' '
            for sec in sections:
                extra += sec + ' / '
            extras.append( extra + name )
        if len(extras) != 0:
            msg = "Broadcast validation failed: illegal items:"
            for extra in extras:
                msg += '\n' + extra 
            return ( False, msg )
        return ( True, "OK" )

    def prune( self, target ):
        # remove empty leaves left by unsetting broadcast values
        for key, val in target.items():
            if isinstance( val, dict ):
                if val == {}:
                    del target[key]
                else:
                    self.prune( target[key] )
            else:
                if not val:
                    del target[key]
 
    def addict( self, target, source ):
        for key, val in source.items():
            if isinstance( val, dict ):
                if key not in target:
                    target[key] = {}
                self.addict( target[key], val )
            else:
                if source[key]:
                    target[key] = source[key]
                elif key in target:
                    del target[key]

    def put( self, namespaces, cycles, settings ):
        valset = {}
        for s in settings:
            valset['(namespace)'] = s
        res, msg = self.validate( {'runtime' : valset } )
        if not res:
            return ( res, msg )

        for setting in settings:
            for cycle in cycles:
                if cycle not in self.settings:
                    self.settings[cycle] = {}
                for namespace in namespaces:
                    if namespace not in self.settings[cycle]:
                        self.settings[cycle][namespace] = {}
                    self.addict( self.settings[cycle][namespace], setting )
        # prune emtpy settings tree branches
        while True:
            tmp = deepcopy( self.settings )
            self.prune( self.settings )
            if tmp == self.settings:
                break

        if self.get_dump() != self.last_settings:
            self.settings_queue.append(RecordBroadcastObject(datetime.now(), self.get_dump() ))
            self.last_settings = self.settings
            self.new_settings = True

        return ( True, 'OK' )

    def get( self, task_id=None ):
        # Retrieve all broadcast variables that target a given task ID.
        if not task_id:
            # all broadcast settings requested
            return self.settings
        name, tag = task_id.split( TaskID.DELIM )

        apply = {}
        for cycle in [ 'all', tag ]:
            # 'all' first so it can be overridden by specific cycle
            if cycle not in self.settings:
                continue
            nslist = []
            for ns in self.linearized_ancestors[name]:
                if ns in self.settings[cycle]:
                    nslist.append( ns )
            # nslist contains namespaces from current broadcast settings
            # that are in the task's family tree, in linearized ancestor
            # order, e.g. ['ops_atovs', 'OPS', 'root' ] means a
            # broadcast setting is in place for root, OPS, and
            # ops_atovs. Use the highest level one (i.e. a task specific
            # setting takes precedence over root or mid-level
            # namespaces).
            if nslist:
                self.addict( apply, self.settings[cycle][nslist[0]] )

        return apply

    def expire( self, expire=None ):
        if not expire:
            self.log.warning( 'Expiring all broadcast settings now' ) 
            self.settings = {}
        for ctime in self.settings.keys():
            if ctime == 'all':
                continue
            elif ctime < expire:
                self.log.warning( 'Expiring ' + ctime + ' broadcast settings now' ) 
                del self.settings[ ctime ]

    def clear( self ):
        self.settings = {}
        if self.get_dump() != self.last_settings:
            self.settings_queue.append(RecordBroadcastObject(datetime.now(), self.get_dump() ))
            self.last_settings = self.settings
            self.new_settings = True

    def dump( self, FILE ):
        # write broadcast variables to the suite state dump file
        FILE.write( pickle.dumps( self.settings) + '\n' )

    def get_db_ops(self):
        ops = []
        for d in self.settings_queue:
            if d.to_run:
                ops.append(d)
                d.to_run = False
        self.new_settings = False
        return ops
    
    def get_dump( self ):
        # return the broadcast variables as written to the suite state dump file
        return pickle.dumps( self.settings ) + '\n'

    def load( self, pickled_settings ):
        self.settings = pickle.loads( pickled_settings )

