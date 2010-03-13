#!/usr/bin/python


from task_types import forecast_model, free_task
from mod_oneoff import oneoff
from mod_sequential import sequential
from mod_dummy import dummy
from mod_contact import contact
from mod_catchup_contact import catchup_contact
from prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites import prerequisites
from outputs import outputs
from time import sleep

import cycle_time
import task_launcher
import task_state

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging

class B(forecast_model):
    # AUTO-GENERATED FROM taskdef/B.def

    name = 'B'
    short_name = 'B'
    instance_count = 0

    description = [
        'Forecast model.',
        'Generates restart files for the next two cycles.',
        'Depends on task A finishing.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'A%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 60 )

        self.env_vars = [
            ['WRAP', 'B.sh'],
            ['NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 6)],
            ['NEXT_NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 12)],
        ]

        restart_times = [20,40]
        self.register_restarts( restart_times )


        forecast_model.__init__( self, dummy_mode, initial_state )

class E(free_task):
    # AUTO-GENERATED FROM taskdef/E.def

    name = 'E'
    short_name = 'E'
    instance_count = 0

    description = [
        'Post processing for task B.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'B%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 150 )

        self.env_vars = [
            ['WRAP', 'E.sh'],
        ]


        free_task.__init__( self, dummy_mode, initial_state )

class ext(contact, free_task):
    # AUTO-GENERATED FROM taskdef/ext.def

    name = 'ext'
    short_name = 'ext'
    instance_count = 0

    description = [
        'Example system task to provide the external input required by task A.',
        'Depends only on the system startup task at start time.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.real_time_delay = 1.0

        self.prerequisites = prerequisites( self.name, self.c_time )

        if startup:
            # overwrite prerequisites for startup case
            self.prerequisites = prerequisites( self.name, self.c_time )
            self.prerequisites.add( 'startup%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 10 )

        self.env_vars = [
            ['WRAP', 'ext.sh'],
        ]


        free_task.__init__( self, dummy_mode, initial_state )

class A(forecast_model):
    # AUTO-GENERATED FROM taskdef/A.def

    name = 'A'
    short_name = 'A'
    instance_count = 0

    description = [
        'Forecast model.',
        'Generates restart files for the next cycle only.',
        'Depends on the external data task finishing.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'ext%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 90 )

        self.env_vars = [
            ['WRAP', 'A.sh'],
            ['NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 6)],
        ]

        restart_times = [89]
        self.register_restarts( restart_times )


        forecast_model.__init__( self, dummy_mode, initial_state )

class F(free_task):
    # AUTO-GENERATED FROM taskdef/F.def

    name = 'F'
    short_name = 'F'
    instance_count = 0

    description = [
        'Post processing for task C.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'C%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 50 )

        self.env_vars = [
            ['WRAP', 'F.sh'],
        ]


        free_task.__init__( self, dummy_mode, initial_state )

class startup(oneoff, free_task):
    # AUTO-GENERATED FROM taskdef/startup.def

    name = 'startup'
    short_name = 'startup'
    instance_count = 0

    description = [
        'Clean out the system working directory at startup.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = True

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 10 )

        self.env_vars = [
            ['WRAP', 'startup.sh'],
        ]


        free_task.__init__( self, dummy_mode, initial_state )

class D(free_task):
    # AUTO-GENERATED FROM taskdef/D.def

    name = 'D'
    short_name = 'D'
    instance_count = 0

    description = [
        'Post processing for tasks B and C.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'B%'  + self.c_time + ' finished' )
        self.prerequisites.add( 'C%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 75 )

        self.env_vars = [
            ['WRAP', 'D.sh'],
        ]


        free_task.__init__( self, dummy_mode, initial_state )

class C(forecast_model):
    # AUTO-GENERATED FROM taskdef/C.def

    name = 'C'
    short_name = 'C'
    instance_count = 0

    description = [
        'Forecast model.',
        'Generates restart files for the next two cycles.',
        'Depends on task A finishing.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'A%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 120 )

        self.env_vars = [
            ['WRAP', 'C.sh'],
            ['NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 6)],
            ['NEXT_NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 12)],
        ]

        restart_times = [40, 80]
        self.register_restarts( restart_times )


        forecast_model.__init__( self, dummy_mode, initial_state )

class cold(oneoff, free_task):
    # AUTO-GENERATED FROM taskdef/cold.def

    name = 'cold'
    short_name = 'cold'
    instance_count = 0

    description = [
        'Provides restart prerequisites for tasks A, B, and C.',
        'These would normally be generated by previous instances.',
        'Depends on the system startup task.',
    ]

    owner = 'oliverh'
    external_task = 'cylc-task-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = True

    def __init__( self, c_time, dummy_mode, initial_state = None, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )

        if startup:
            # overwrite prerequisites for startup case
            self.prerequisites = prerequisites( self.name, self.c_time )
            self.prerequisites.add( 'startup%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 10 )

        self.outputs.add( 7, 'A restart files ready for ' + self.c_time )
        self.outputs.add( 8, 'B restart files ready for ' + self.c_time )
        self.outputs.add( 9, 'C restart files ready for ' + self.c_time )
        self.env_vars = [
            ['WRAP', 'cold.sh'],
        ]


        free_task.__init__( self, dummy_mode, initial_state )

