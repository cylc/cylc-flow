#!/usr/bin/python

"""
Dummy Task classes for the Ecoconnect Controller.
See documentation in task.py

This file defines a set of seven dummy tasks, A,B,C,D,E,F, and G
with the following input/output dependencies:

                             (F)--1--2--3--X
                              |       
                      (D)--1--2--3--X
                       |         |
            (A)--1--2--X        (G)--1--2--3--X
                 |  |            |
                 | (C)--1--2--3--X
                 |         |
                 |        (E)--1--2--X
                 |         |       
                (B)--1--2--3--X   

If they run (and generate their postrequisites) at the same rate,
they should start executing in the following order: 

             |   |  |  |   |   |  |
             A   B  C  D   E   F  G 
"""

from task import task
from reference_time import reference_time
from requisites import requisites

import os
import Pyro.core
from copy import deepcopy

class A( task ):
    "dummy task A"

    def __init__( self, ref_time, set_finished ):

        self.name = "A"

        self.valid_hours = [ "00", "06", "12", "18" ]

        time = ref_time.to_str()

        self.prerequisites = requisites( [] )

        self.postrequisites = requisites( [ 
                 "file A_1_" + time + " completed",
                 "file A_2_" + time + " completed",
                 "task A completed for " + time  ] )

        task.__init__( self, ref_time, set_finished )


class B( task ):
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

        task.__init__( self, ref_time, set_finished )


class C( task ):
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

        task.__init__( self, ref_time, set_finished )


class D( task ):
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

        task.__init__( self, ref_time, set_finished )


class E( task ):
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

        task.__init__( self, ref_time, set_finished )


class F( task ):
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

        task.__init__( self, ref_time, set_finished )


class G( task ):
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

        task.__init__( self, ref_time, set_finished )


class H( task ):
    "dummy task H"

    def __init__( self, ref_time, set_finished ):

        self.valid_hours = [ "03" ]

        self.name = 'H'

        time = ref_time.to_str()
        prev_reftime = deepcopy( ref_time )
        prev_reftime.subtract( 3 )
        prev_time = prev_reftime.to_str()

        self.prerequisites = requisites( [
                "task C completed for " + prev_time ] )

        self.postrequisites = requisites( [ 
                 "file H_1_" + time + " completed",
                 "file H_2_" + time + " completed",
                 "file H_3_" + time + " completed",
                 "task H completed for " + time  ] )

        task.__init__( self, ref_time, set_finished )
