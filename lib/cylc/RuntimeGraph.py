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

import os, sys
from mkdir_p import mkdir_p
from cycle_time import ct
import datetime
from graphing import CGraph

class rGraph( object ):
    def __init__(self, suite, config, initial_oldest_ctime, start_tag ):
        self.config = config
        self.initial_oldest_ctime = initial_oldest_ctime
        self.start_tag = start_tag

        title = 'suite ' + suite + ' run-time dependency graph'
        # create output directory if necessary
        odir = config['visualization']['runtime graph']['directory']
        # raises OSError:
        mkdir_p( odir )

        self.file = os.path.join( odir, 'runtime-graph.dot' )
        self.graph = CGraph( title, config['visualization'] )
        self.finalized = False
        self.cutoff = config['visualization']['runtime graph']['cutoff']

    def update( self, task, oldest_ctime=None, oldest_async_tag=None ):
        if self.finalized:
            return
        if task.is_cycling():
            self.update_cycling( task, oldest_ctime )
        else:
            self.update_async( task, oldest_async_tag )
 
    def update_cycling( self, task, oldest ):
        # stop if all tasks are more than cutoff hours beyond suite start time
        if self.start_tag:
            st = ct( self.start_tag )
        else:
            st = ct( self.initial_oldest_ctime )

        ot = ct( oldest )
        delta1 = ot.subtract( st )
        delta2 = datetime.timedelta( 0, 0, 0, 0, 0, self.cutoff, 0 )
        if delta1 >= delta2:
            self.finalize()
            return
        # ignore task if its ctime more than configured hrs beyond suite start time?
        st = st
        tt = ct( task.c_time )
        delta1 = tt.subtract(st)
        if delta1 >= delta2:
            return
        for id in task.get_resolved_dependencies():
            l = id
            r = task.id 
            self.graph.add_edge( l,r,False )
            self.write()

    def update_async( self, task, oldest ):
        # stop if all tasks are beyond the first tag
        ot = oldest
        if ot > 1:
            self.finalize()
            return
        # ignore tasks beyond the first tag 
        tt = int( task.tag )
        if tt > 1:
            return
        for id in task.get_resolved_dependencies():
            l = id
            r = task.id 
            self.graph.add_edge( l,r,False )
            self.write()

    def write( self ):
        #print "Writing graph", self.file
        self.graph.write( self.file )

    def finalize( self ):
        #if self.finalized:
        #    return
        #print "Finalizing graph", self.file
        self.write()
        self.finalized = True

