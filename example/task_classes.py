#!/usr/bin/python


from task_base import task_base, free_task
import job_submit

import reference_time
from requisites import requisites, timed_requisites, fuzzy_requisites
from time import sleep

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging

class A(free_task):
    # AUTO-GENERATED FROM taskdef/task-a.def

    name = 'A'
    owner = 'ecoconnect_test'
    external_task = 'task-wrapper'

    valid_hours = [0,6,12,18]

    env_vars = [
        ['WRAP', 'task-a.sh'] ]

    def __init__( self, ref_time, initial_state):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, [ ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + ' started for ' + ref_time],
            [1, self.name + ' finished for ' + ref_time] ])

        free_task.__init__( self, ref_time, initial_state )

    def run_external_task( self ):
        free_task.run_external_task( self, A.env_vars )

class B(task_base):
    # AUTO-GENERATED FROM taskdef/task-b.def

    name = 'B'
    owner = 'ecoconnect_test'
    external_task = 'task-wrapper'

    valid_hours = [0,6,12,18]

    env_vars = [
        ['WRAP', 'task-b.sh'] ]

    def __init__( self, ref_time, initial_state):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, [
            'A finished for ' + ref_time ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + ' started for ' + ref_time],
            [1, self.name + ' finished for ' + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

    def run_external_task( self ):
        task_base.run_external_task( self, B.env_vars )

class C(task_base):
    # AUTO-GENERATED FROM taskdef/task-c.def

    name = 'C'
    owner = 'ecoconnect_test'
    external_task = 'task-wrapper'

    valid_hours = [0,6,12,18]

    env_vars = [
        ['WRAP', 'task-c.sh'] ]

    def __init__( self, ref_time, initial_state):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, [
            'A finished for ' + ref_time,
            'B finished for ' + ref_time ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + ' started for ' + ref_time],
            [1, self.name + ' finished for ' + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

    def run_external_task( self ):
        task_base.run_external_task( self, C.env_vars )

