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

import re, sys
from cylc.cycling.loader import get_point

# PREREQUISITES: A collection of messages representing the prerequisite
# conditions for a task, each of which can be "satisfied" or not.  An
# unsatisfied prerequisite becomes satisfied if it matches a satisfied
# output message from another task (via the cylc requisite broker).

class plain_prerequisites(object):

    # Extracts T from "foo.T succeeded" etc.
    CYCLE_POINT_RE = re.compile('^\w+\.(\S+) .*$')

    def __init__( self, owner_id, start_point=None ):
        self.labels = {}   # labels[ message ] = label
        self.messages = {}   # messages[ label ] = message
        self.satisfied = {}    # satisfied[ label ] = True/False
        self.satisfied_by = {}   # self.satisfied_by[ label ] = task_id
        self.target_point_strings = []   # list of target cycle points (tags)
        self.auto_label = 0
        self.owner_id = owner_id
        self.start_point = start_point

    def add( self, message, label = None ):
        # Add a new prerequisite message in an UNSATISFIED state.
        if self.start_point:
            task = re.search( r'(.*).(.*) ', message)
            if task.group:
                try:
                    foo = task.group().split(".")[1].rstrip()
                    if ( get_point( foo ) <  self.start_point ):
                        return
                except IndexError:
                    pass
        if label:
            pass
        else:
            self.auto_label += 1
            label = str( self.auto_label )

        if message in self.labels:
            # IGNORE A DUPLICATE PREREQUISITE (the same trigger must
            # occur in multiple non-conditional graph string sections).
            # Warnings disabled pending a global check across all
            # prerequisites held by a task.
            ##print >> sys.stderr, "WARNING, " + self.owner_id + ": duplicate prerequisite: " + message
            return

        self.messages[ label ] = message
        self.labels[ message ] = label
        self.satisfied[label] = False
        self.satisfied_by[label] = None
        m = re.match( self.__class__.CYCLE_POINT_RE, message )
        if m:
            self.target_point_strings.append( m.groups()[0] )

    def remove( self, message ):
        lbl = self.labels[message]
        del self.labels[message]
        del self.messages[lbl]
        del self.satisfied[lbl]
        del self.satisfied_by[lbl]
        m = re.match( self.__class__.CYCLE_POINT_RE, message )
        if m and m.groups()[0] in self.target_point_strings:
            self.target_point_strings.remove( m.groups()[0] )

    def all_satisfied( self ):
        return not ( False in self.satisfied.values() )

    def get_satisfied_by( self ):
        return self.satisfied_by

    def count( self ):
        # how many messages are stored
        return len( self.satisfied.keys() )

    def dump( self ):
        # return an array of strings representing each message and its state
        res = []
        for key in self.satisfied:
            res.append( [ self.messages[key], self.satisfied[ key ] ]  )
        return res

    def set_all_satisfied( self ):
        for label in self.messages:
            self.satisfied[ label ] = True

    def set_all_unsatisfied( self ):
        for label in self.messages:
            self.satisfied[ label ] = False

    def get_target_points( self ):
        """Return a list of cycle points target by each prerequisite,
        including each component of conditionals."""
        return [ get_point(p) for p in self.target_point_strings ]
