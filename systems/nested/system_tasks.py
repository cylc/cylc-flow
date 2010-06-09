#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|



from task_types import forecast_model, free_task
from mod_oneoff import oneoff
from mod_sequential import sequential
from mod_contact import contact
from mod_catchup_contact import catchup_contact
from prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites import prerequisites
from outputs import outputs
from time import sleep

import cycle_time
import task_state

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging

from dynamic_instantiation import get_object

import job_submit_methods
class F(free_task):
    # AUTO-GENERATED FROM taskdef/F.def

    name = 'F'
    short_name = 'F'
    instance_count = 0

    description = [
        'Post processing for the storm surge model',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'cylc-wrapper'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'storm surge fields ready for ' + self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 50.0 )

        self.outputs.add( 50.0, 'storm surge products ready for ' + self.c_time )
        self.env_vars = [
            ['WRAP', 'F.sh'],
            ['ANALYSIS_TIME', self.c_time],
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        free_task.__init__( self, initial_state )

class userguide_subsystem(sequential, free_task):
    # AUTO-GENERATED FROM taskdef/userguide.def

    name = 'userguide_subsystem'
    short_name = 'userguide_subsystem'
    instance_count = 0

    description = [
        'nested single cycle subsystem',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'userguide.sh'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'surface pressure field ready for ' + self.c_time )
        self.prerequisites.add( 'surface wind fields ready for ' + self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 120.0 )

        self.outputs.add( 118.0, 'storm surge fields ready for ' + self.c_time )
        self.env_vars = [
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        free_task.__init__( self, initial_state )

class E(free_task):
    # AUTO-GENERATED FROM taskdef/E.def

    name = 'E'
    short_name = 'E'
    instance_count = 0

    description = [
        'Post processing for the sea state model.',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'E.sh'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'sea state fields ready for ' + self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 150.0 )

        self.outputs.add( 150.0, 'sea state products ready for ' + self.c_time )
        self.env_vars = [
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        free_task.__init__( self, initial_state )

class X(contact, free_task):
    # AUTO-GENERATED FROM taskdef/X.def

    name = 'X'
    short_name = 'X'
    instance_count = 0

    description = [
        'Retrieve external observation data at cycle-time + 1 hour.',
        'Depends only on the system startup task at start time.',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'X.sh'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

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

        self.register_run_length( 5.0 )

        self.outputs.add( 5.0, 'obs data ready for ' + self.c_time )
        self.env_vars = [
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        free_task.__init__( self, initial_state )

class A(forecast_model):
    # AUTO-GENERATED FROM taskdef/A.def

    name = 'A'
    short_name = 'A'
    instance_count = 0

    description = [
        'Could be an atmospheric model.',
        'Requires real time obs data, and own restart file.',
        'Generates restart files for the next cycle only.',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'A.sh'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'obs data ready for ' + self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 90.0 )

        self.outputs.add( 80.0, 'level forecast fields ready for ' + self.c_time )
        self.outputs.add( 80.0, 'surface wind fields ready for ' + self.c_time )
        self.outputs.add( 80.0, 'surface pressure field ready for ' + self.c_time )
        self.env_vars = [
            ['NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 6)],
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        restart_times = [20.0]
        self.register_restarts( restart_times )

        forecast_model.__init__( self, initial_state )

class D(free_task):
    # AUTO-GENERATED FROM taskdef/D.def

    name = 'D'
    short_name = 'D'
    instance_count = 0

    description = [
        'Combined post processing for the sea state and storm surge forecasts.',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'D.sh'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'sea state fields ready for ' + self.c_time )
        self.prerequisites.add( 'storm surge fields ready for ' + self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 75.0 )

        self.outputs.add( 75.0, 'seagram products ready for ' + self.c_time )
        self.env_vars = [
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        free_task.__init__( self, initial_state )

class B(forecast_model):
    # AUTO-GENERATED FROM taskdef/B.def

    name = 'B'
    short_name = 'B'
    instance_count = 0

    description = [
        'Could be a sea state model, driven by the atmospheric model.',
        'Requires surface wind fields, and own restart file.',
        'Generates restart files for the next two cycles.',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'B.sh'

    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'surface wind fields ready for ' + self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 60.0 )

        self.outputs.add( 60.0, 'sea state fields ready for ' + self.c_time )
        self.env_vars = [
            ['NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 6)],
            ['NEXT_NEXT_CYCLE_TIME', cycle_time.increment( self.c_time, 12)],
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        restart_times = [10.0,20.0]
        self.register_restarts( restart_times )

        forecast_model.__init__( self, initial_state )

class coldstart(oneoff, free_task):
    # AUTO-GENERATED FROM taskdef/coldstart.def

    name = 'coldstart'
    short_name = 'coldstart'
    instance_count = 0

    description = [
        'Provides the initial restart prerequisites for the forecast models.',
        'A real system would have separate cold start tasks for each model',
        '(and a dummy one to "fake" the outputs for any model that has to be',
        '"spun up" by external means before starting the scheduler).',
        'Depends on the system startup task.',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'coldstart.sh'

    valid_hours = [0,6,12,18]

    quick_death = True

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'startup%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 50.0 )

        self.outputs.add( 47.0, 'A restart files ready for ' + self.c_time )
        self.outputs.add( 48.0, 'B restart files ready for ' + self.c_time )
        self.outputs.add( 49.0, 'C restart files ready for ' + self.c_time )
        self.env_vars = [
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        free_task.__init__( self, initial_state )

class startup(oneoff, free_task):
    # AUTO-GENERATED FROM taskdef/startup.def

    name = 'startup'
    short_name = 'startup'
    instance_count = 0

    description = [
        'Cleans out the system working directory at startup.',
    ]

    owner = 'ecoconnect_dvel'
    external_task = 'startup.sh'

    valid_hours = [0,6,12,18]

    quick_death = True

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.name, self.c_time )

        self.outputs = outputs( self.name, self.c_time )

        self.register_run_length( 5.0 )

        self.env_vars = [
        ]

        # in dummy mode, replace the external task with _cylc-dummy-task
        if dummy_mode:
                self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.name, self.external_task, self.c_time, self.env_vars )

        free_task.__init__( self, initial_state )

