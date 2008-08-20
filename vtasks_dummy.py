#!/usr/bin/python

"""
Virtual Task classes for the Ecoconnect Controller.
See documentation in vtask-base.py

This file defines a set of seven dummy tasks, A,B,C,D,E,F, and Z
with the following input/output dependencies:

                             (E)--1--2--3--X
                              |       
                      (D)--1--2--3--X
                       |         |
            (A)--1--2--X        (F)--1--2--3--X
                 |  |            |
                 | (C)--1--2--3--X
                 |         |
                 |        (Z)--1--2--X
                 |         |       
                (B)--1--2--3--X   

If they produce their postrequisites (1,2,3,4,X) at the same rate,
they should start executing in the following order: 

             |   |  |  |   |   |  |
             A   B  C  D  (Z)  E  F
"""

from vtask_base import vtask
from reference_time import reference_time
from requisites import requisites

import os
import Pyro.core

class A( vtask ):
    "dummy task A"

    name = "A"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [] )

        self.postrequisites = requisites( [ 
                 "file A_1_" + ref_time.to_str() + " completed",
                 "file A_2_" + ref_time.to_str() + " completed",
                 "task A completed for " + ref_time.to_str()  ] )

        vtask.__init__( self, ref_time )


class B( vtask ):
    "dummy task B"

    name = "B"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [
                "file A_1_" + ref_time.to_str() + " completed"] )

        self.postrequisites = requisites( [ 
                 "file B_1_" + ref_time.to_str() + " completed",
                 "file B_2_" + ref_time.to_str() + " completed",
                 "file B_3_" + ref_time.to_str() + " completed",
                 "task B completed for " + ref_time.to_str()  ] )

        vtask.__init__( self, ref_time )


class C( vtask ):
    "dummy task C"

    name = "C"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [
                "file A_2_" + ref_time.to_str() + " completed"] )

        self.postrequisites = requisites( [ 
                 "file C_1_" + ref_time.to_str() + " completed",
                 "file C_2_" + ref_time.to_str() + " completed",
                 "file C_3_" + ref_time.to_str() + " completed",
                 "task C completed for " + ref_time.to_str()  ] )

        vtask.__init__( self, ref_time )


class D( vtask ):
    "dummy task D"

    name = "D"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [
                "task A completed for " + ref_time.to_str() ] )

        self.postrequisites = requisites( [ 
                 "file D_1_" + ref_time.to_str() + " completed",
                 "file D_2_" + ref_time.to_str() + " completed",
                 "file D_3_" + ref_time.to_str() + " completed",
                 "task D completed for " + ref_time.to_str()  ] )

        vtask.__init__( self, ref_time )


class E( vtask ):
    "dummy task E"

    name = "E"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [
                "file D_2_" + ref_time.to_str() + " completed"] )

        self.postrequisites = requisites( [ 
                 "file E_1_" + ref_time.to_str() + " completed",
                 "file E_2_" + ref_time.to_str() + " completed",
                 "file E_3_" + ref_time.to_str() + " completed",
                 "task E completed for " + ref_time.to_str()  ] )

        vtask.__init__( self, ref_time )


class F( vtask ):
    "dummy task F"

    name = "F"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [
                "file D_3_" + ref_time.to_str() + " completed",
                "task C completed for " + ref_time.to_str() ] )

        self.postrequisites = requisites( [ 
                 "file F_1_" + ref_time.to_str() + " completed",
                 "file F_2_" + ref_time.to_str() + " completed",
                 "file F_3_" + ref_time.to_str() + " completed",
                 "task F completed for " + ref_time.to_str()  ] )

        vtask.__init__( self, ref_time )


class Z( vtask ):
    "dummy task Z"

    name = "Z"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [
                "file C_2_" + ref_time.to_str() + " completed",
                "file B_3_" + ref_time.to_str() + " completed" ] )

        self.postrequisites = requisites( [ 
                 "file Z_1_" + ref_time.to_str() + " completed",
                 "file Z_2_" + ref_time.to_str() + " completed",
                 "task Z completed for " + ref_time.to_str()  ] )

        vtask.__init__( self, ref_time )
