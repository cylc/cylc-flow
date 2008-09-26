#!/usr/bin/python

"""
Dummy Task classes for the Ecoconnect Controller.
See documentation in task.py

TASK NAMES MUST NOT CONTAIN UNDERSCORES

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

all_task_names = [ 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H' ]

class A( task_base ):
    "dummy task A"

    """
    this task provides initial input to get things going:
    it starts running immediately (no prequisites except
    its previous instance) and it completes when it's outputs
    are generated for use by the downstream tasks.
    """

    runs_on_kupe = True

    def __init__( self, ref_time, set_finished ):

        self.name = "A:kupe"

        self.valid_hours = [ "00", "06", "12", "18" ]

        #prev_time = ref_time.decrement().to_str()
        time = ref_time.to_str()

        self.prerequisites = requisites( [] )

        self.postrequisites = requisites( [ 
                 "file A_1_" + time + " completed",
                 "file A_2_" + time + " completed",
                 "task A completed for " + time  ] )

        task_base.__init__( self, ref_time, set_finished )



class B( task_base ):
    "dummy task B"

    runs_on_kupe = True

    def __init__( self, ref_time, set_finished ):

        self.name = 'B:kupe'

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
