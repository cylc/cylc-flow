#!/usr/bin/python

"""
Dummy Task classes for the Ecoconnect Controller.
See documentation in task.py

This file defines a set of dummy tasks with dependencies defined such
that they should execute in the following "sequence":

                             (F)--1--2--3--X
                              |
                      (D)--1--2--3--X
                       |         |
            (A)--1--2--X        (G)--1--2--3--X
                 |  |            |
                 | (C)--1--2--3--X
                 |         |     |
                 |         |    (H)--1--2--3--4--X
                 |         |
                 |        (E)--1--2--X
                 |         |
                (B)--1--2--3--X

If the tasks run (and generate their postrequisites) at the same rate,
they should begin executing in the following order: 

             |   |  |  |   |   |  ||
             A   B  C  D   E   F  GH
"""

from task_base import task_base
from reference_time import reference_time
from requisites import requisites

import os
import Pyro.core
from copy import deepcopy

"""
Thoughts on task management to allow cycle overlap

0/ task zero is the special task that provides initial input to get a
cycle started (e.g. the downloader). It must be able to start running
immediately, or else nothing will start.  

1/ no task can start IF any previous instance of itself exists that
isn't in a "finished" state. This prevents successive tasks instances
from running out of order.  This can be handle automatically rather than
as explicitly defined prerequisites?  Tasks run if no previous instance
exists, to handle startup, and models that don't run every cycle.

I think this is necessary when cycle overlap is allowed. E.g. consider a
task E in two successive cycles when a very computational intensive task
that E does not depend on is omitted from the second cycle: the E(T2)
*could* be ready to go before E(T1)??? 

3/ if task zero depends on a SPECIAL previous task (nzwave), this will
determine the amount of overlap (if it depends on the final previous
task there will be no overlap)

4/ task manager creates a new batch(T+1) as soon as task zero(T)
completes.  They will be in the "waiting" state until task zero(T+1)
goes off.  T-based batch creation prevents tasks with no prerequisites
(nztide) from running off ahead (otherwise all task would also need to
depend on task zero?). It is also convenient from a config file 
perspective (we need to be able to specify T-based batches for 
each cycle).

5/ task manager deletes all tasks(T) when they are all finished (we 
can do this because of the IF in 1/ above)
"""

class A( task_base ):
    "dummy task zero"

    """
    this task provides initial input to get things going:
    it starts running immediately (no prequisites except
    its previous instance) and it completes when it's outputs
    are generated for use by the downstream tasks.
    """

    def __init__( self, ref_time, set_finished ):

        self.name = "A"

        self.valid_hours = [ "00", "06", "12", "18" ]

        #prev_time = ref_time.decrement().to_str()
        time = ref_time.to_str()

        self.prerequisites = requisites( [] )

        self.postrequisites = requisites( [ 
                 "foo 1",
                 "foo 2",
                 "foo 3",
                 "foo 4",
                 "foo 5",
                 "foo 6",
                 "foo 7",
                 "foo 8",
                 "foo 9",
                 "foo 10",
                 "file A_1_" + time + " completed",
                 "file A_2_" + time + " completed",
                 "task A completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )


class B( task_base ):
    "dummy task B"

    def __init__( self, ref_time, set_finished ):

        self.name = 'B'

        self.valid_hours = [ "00", "06", "12", "18" ]

        time = ref_time.to_str()

        self.prerequisites = requisites( [
                "file A_1_" + time + " completed"] )

        self.postrequisites = requisites( [ 
                 "file B_1_" + time + " completed",
                 "file B_2_" + time + " completed",
                 "file B_3_" + time + " completed",
                 "task B completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )


class C( task_base ):
    "dummy task C"

    def __init__( self, ref_time, set_finished ):

        self.valid_hours = [ "00", "06", "12", "18" ]

        self.name = 'C'

        time = ref_time.to_str()

        self.prerequisites = requisites( [
                "file A_2_" + time + " completed"] )

        self.postrequisites = requisites( [ 
                 "file C_1_" + time + " completed",
                 "file C_2_" + time + " completed",
                 "file C_3_" + time + " completed",
                 "task C completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )


class D( task_base ):
    "dummy task D"

    def __init__( self, ref_time, set_finished ):

        self.valid_hours = [ "00", "06", "12", "18" ]

        self.name = 'D'

        time = ref_time.to_str()

        self.prerequisites = requisites( [
                "task A completed for " + time ] )

        self.postrequisites = requisites( [ 
                 "file D_1_" + time + " completed",
                 "file D_2_" + time + " completed",
                 "file D_3_" + time + " completed",
                 "task D completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )


class E( task_base ):
    "dummy task E"

    def __init__( self, ref_time, set_finished ):

        self.valid_hours = [ "00", "12" ]

        self.name = 'E'

        time = ref_time.to_str()

        self.prerequisites = requisites( [
                "file C_2_" + time + " completed",
                "file B_3_" + time + " completed" ] )

        self.postrequisites = requisites( [ 
                 "file E_1_" + time + " completed",
                 "file E_2_" + time + " completed",
                 "task E completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )


class F( task_base ):
    "dummy task F"

    def __init__( self, ref_time, set_finished ):

        self.valid_hours = [ "06", "18" ]

        self.name = 'F'

        time = ref_time.to_str()

        self.prerequisites = requisites( [
                "file D_2_" + time + " completed"] )

        self.postrequisites = requisites( [ 
                 "file F_1_" + time + " completed",
                 "file F_2_" + time + " completed",
                 "file F_3_" + time + " completed",
                 "task F completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )


class G( task_base ):
    "dummy task G"

    def __init__( self, ref_time, set_finished ):

        self.valid_hours = [ "00", "06", "12", "18" ]

        self.name = 'G'

        time = ref_time.to_str()

        self.prerequisites = requisites( [
                "file D_3_" + time + " completed",
                "task C completed for " + time ] )

        self.postrequisites = requisites( [ 
                 "file G_1_" + time + " completed",
                 "file G_2_" + time + " completed",
                 "file G_3_" + time + " completed",
                 "task G completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )


class H( task_base ):
    "dummy task H"

    def __init__( self, ref_time, set_finished ):

        self.valid_hours = [ "03" ]

        self.name = 'H'

        time = ref_time.to_str()
        #prev_reftime = deepcopy( ref_time )
        #prev_reftime.subtract( 3 )
        #prev_time = prev_reftime.to_str()

        self.prerequisites = requisites( [
                "task C completed for " + time ] )

        self.postrequisites = requisites( [ 
                 "file H_1_" + time + " completed",
                 "file H_2_" + time + " completed",
                 "file H_3_" + time + " completed",
                 "file H_4_" + time + " completed",
                 "task H completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )
