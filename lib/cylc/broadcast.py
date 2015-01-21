#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import Pyro.core
from copy import deepcopy
from datetime import datetime
import logging, os, sys
import cPickle as pickle
from cylc.task_id import TaskID
from cycling.loader import get_point
from rundb import RecordBroadcastObject
from wallclock import get_current_time_string

class broadcast( Pyro.core.ObjBase ):
    """Receive broadcast variables from cylc clients."""

    # examples:
    #self.settings[ 'all-cycle-points' ][ 'root' ] = "{ 'environment' : { 'FOO' : 'bar' }}
    #self.settings[ '2010080806' ][ 'root' ] = "{ 'command scripting' : 'stuff' }

    def __init__( self, linearized_ancestors ):
        self.log = logging.getLogger('main')
        self.settings = {}
        self.last_settings = self.get_dump()
        self.settings_queue = []
        self.linearized_ancestors = linearized_ancestors
        Pyro.core.ObjBase.__init__(self)

    def prune( self, target ):
        # remove empty leaves left by unsetting broadcast values
        def _prune( target ):
            # recursive sub-function
            pruned = False
            for key, val in target.items():
                if isinstance( val, dict ):
                    if not val:
                        del target[key]
                        pruned = True
                    else:
                        pruned = _prune( target[key] )
                else:
                    if not val:
                        del target[key]
                        pruned = True
            return pruned
        # prune until no further changes
        while _prune( target ):
            continue

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
        """Add new broadcast settings, or prune newly unset ones"""
        for setting in settings:
            for cycle in cycles:
                if cycle not in self.settings.keys():
                    self.settings[cycle] = {}
                for namespace in namespaces:
                    if namespace not in self.settings[cycle]:
                        self.settings[cycle][namespace] = {}
                    self.addict( self.settings[cycle][namespace], setting )
        # prune any empty branches
        self.prune( self.settings )

        if self.get_dump() != self.last_settings:
            current_time_string = get_current_time_string(
                display_sub_seconds=True)
            self.settings_queue.append(RecordBroadcastObject(
                current_time_string, self.get_dump() ))
            self.last_settings = self.settings

        return ( True, 'OK' )

    def get( self, task_id=None ):
        # Retrieve all broadcast variables that target a given task ID.
        if not task_id:
            # all broadcast settings requested
            return self.settings
        name, point_string = TaskID.split(task_id)

        ret = {}
        # The order is:
        #    all:root -> all:FAM -> ... -> all:task
        # -> tag:root -> tag:FAM -> ... -> tag:task
        # DEPRECATED at cylc 6: 'all-cycles'
        for cycle in [ 'all-cycle-points', 'all-cycles', point_string ]:
            if cycle not in self.settings:
                continue
            for ns in reversed(self.linearized_ancestors[name]):
                if ns in self.settings[cycle]:
                    self.addict( ret, self.settings[cycle][ns] )
        return ret

    def expire( self, cutoff ):
        """Clear all settings targetting cycle points earlier than cutoff."""
        if not cutoff:
            self.log.info( 'Expiring all broadcast settings now' )
            self.settings = {}
        for point_string in self.settings.keys():
            # DEPRECATED at cylc 6: 'all-cycles'
            if point_string in ['all-cycle-points', 'all-cycles']:
                continue
            point = get_point(point_string)
            if point < cutoff:
                self.log.info( 'Expiring ' + str(point) + ' broadcast settings now' )
                del self.settings[ point_string ]

    def clear( self, namespaces, point_strings ):
        """
        Clear settings globally, or for listed namespaces and/or points.
        """
        if not namespaces and not point_strings:
            # clear all settings
            self.settings = {}
        elif point_strings:
            # clear all settings specific to given point_strings
            for point_string in point_strings:
                try:
                    del self.settings[point_string]
                except:
                    pass
        elif namespaces:
            # clear all settings specific to given namespaces
            for point_string in self.settings.keys():
                for ns in namespaces:
                    try:
                        del self.settings[point_string][ns]
                    except:
                        pass
        if self.get_dump() != self.last_settings:
            self.settings_queue.append(RecordBroadcastObject(
                get_current_time_string(display_sub_seconds=True),
                self.get_dump()
            ))
            self.last_settings = self.settings

    def dump( self, FILE ):
        # write broadcast variables to the suite state dump file
        FILE.write( pickle.dumps( self.settings) + '\n' )

    def get_db_ops(self):
        ops = self.settings_queue
        self.settings_queue = []
        return ops

    def get_dump( self ):
        # return the broadcast variables as written to the suite state dump file
        return pickle.dumps( self.settings ) + '\n'

    def load( self, pickled_settings ):
        self.settings = pickle.loads( pickled_settings )
