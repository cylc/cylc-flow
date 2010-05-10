#!/usr/bin/python



#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from cycling_daemon import cycling_daemon
from asynchronous import asynchronous
from forecast_model import forecast_model
from free_task import free_task
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

class watcher(cycling_daemon):

    name = 'watcher'
    short_name = 'watcher'
    instance_count = 0

    description = [
        'watch continuously for incoming satellite data',
    ]

    owner = None
    remote_host = None
    external_task = 'watcher.sh'

    valid_hours = [0,6,12,18]

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        if startup:
            self.prerequisites.add( 'startup%' + self.c_time + ' finished')

        self.outputs = outputs( self.id )
        self.output_patterns = []
        self.output_patterns.append( 'external data ready for (\d{10})' )
        self.output_patterns.append( 'crap ready for (\d{10}), ass hole' )
 
        env_vars = {}
        commandline = {}
        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

 
        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        cycling_daemon.__init__( self, initial_state, no_reset )

class B(forecast_model):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/B.def

    name = 'B'
    short_name = 'B'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Could be a sea state model, driven by the atmospheric model.',
        'Requires surface wind fields, and own restart file.',
        'Generates restart files for the next two cycles.',
    ]

    owner = None
    external_task = 'B.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        self.prerequisites.add( 'surface wind fields ready for ' + self.c_time )

        self.outputs = outputs( self.id )

        self.register_run_length( 60.0 )

        self.outputs.add( 60.0, 'sea state fields ready for ' + self.c_time )

        env_vars = {}
        env_vars['NEXT_CYCLE_TIME'] = cycle_time.increment( self.c_time, 6)
        env_vars['NEXT_NEXT_CYCLE_TIME'] = cycle_time.increment( self.c_time, 12)

        commandline = []

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        restart_times = [10.0,20.0]
        self.register_restarts( restart_times )

        forecast_model.__init__( self, initial_state, no_reset )

class X(free_task):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/X.def

    name = 'X'
    short_name = 'X'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Retrieve external observation data when it is ready.',
    ]

    owner = None
    external_task = 'X.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        self.prerequisites.add( 'external data ready for ' + self.c_time )

        self.outputs = outputs( self.id )

        self.register_run_length( 5.0 )

        self.outputs.add( 5.0, 'obs data ready for ' + self.c_time )

        env_vars = {}

        commandline = []

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        free_task.__init__( self, initial_state, no_reset )

class E(free_task):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/E.def

    name = 'E'
    short_name = 'E'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Post processing for the sea state model.',
    ]

    owner = None
    external_task = 'E.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        self.prerequisites.add( 'sea state fields ready for ' + self.c_time )

        self.outputs = outputs( self.id )

        self.register_run_length( 150.0 )

        self.outputs.add( 150.0, 'sea state products ready for ' + self.c_time )

        env_vars = {}

        commandline = []

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        free_task.__init__( self, initial_state, no_reset )

class coldstart(oneoff, free_task):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/coldstart.def

    name = 'coldstart'
    short_name = 'coldstart'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Provides the initial restart prerequisites for the forecast models.',
        'A real system would have separate cold start tasks for each model',
        '(and a dummy one to "fake" the outputs for any model that has to be',
        '"spun up" by external means before starting the scheduler).',
        'Depends on the system startup task.',
    ]

    owner = None
    external_task = 'coldstart.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = True

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )

        if startup:
            # overwrite prerequisites for startup case
            self.prerequisites = prerequisites( self.id )
            self.prerequisites.add( 'startup%'  + self.c_time + ' finished' )

        self.outputs = outputs( self.id )

        self.register_run_length( 50.0 )

        self.outputs.add( 47.0, 'A restart files ready for ' + self.c_time )
        self.outputs.add( 48.0, 'B restart files ready for ' + self.c_time )
        self.outputs.add( 49.0, 'C restart files ready for ' + self.c_time )

        env_vars = {}

        commandline = []

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        free_task.__init__( self, initial_state, no_reset )

class A(forecast_model):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/A.def

    name = 'A'
    short_name = 'A'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Could be an atmospheric model.',
        'Requires real time obs data, and own restart file.',
        'Generates restart files for the next cycle only.',
    ]

    owner = None
    external_task = 'A.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        self.prerequisites.add( 'obs data ready for ' + self.c_time )

        self.outputs = outputs( self.id )

        self.register_run_length( 90.0 )

        self.outputs.add( 80.0, 'level forecast fields ready for ' + self.c_time )
        self.outputs.add( 80.0, 'surface wind fields ready for ' + self.c_time )
        self.outputs.add( 80.0, 'surface pressure field ready for ' + self.c_time )

        env_vars = {}
        env_vars['NEXT_CYCLE_TIME'] = cycle_time.increment( self.c_time, 6)
        env_vars['ANIMAL'] = 'foxy fox'
        env_vars['REMOTE_HOME'] = '$[HOME]'

        commandline = []
        commandline.append('--file=${HOME}/data-' + cycle_time.increment( self.c_time, 6) + '.nc')
        commandline.append('"the quick brown $ANIMAL went $[HOME]"')

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        restart_times = [20.0]
        self.register_restarts( restart_times )

        forecast_model.__init__( self, initial_state, no_reset )

class F(free_task):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/F.def

    name = 'F'
    short_name = 'F'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Post processing for the storm surge model',
    ]

    owner = None
    external_task = 'cylc-wrapper'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        self.prerequisites.add( 'storm surge fields ready for ' + self.c_time )

        self.outputs = outputs( self.id )

        self.register_run_length( 50.0 )

        self.outputs.add( 50.0, 'storm surge products ready for ' + self.c_time )

        env_vars = {}
        env_vars['WRAP'] = 'F.sh'
        env_vars['FOO'] = 'foo'
        env_vars['ANALYSIS_TIME'] = self.c_time

        commandline = []
        commandline.append('--foo=$FOO')

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        free_task.__init__( self, initial_state, no_reset )

class startup(oneoff, free_task):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/startup.def

    name = 'startup'
    short_name = 'startup'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Cleans out the system working directory at startup.',
    ]

    owner = None
    external_task = 'startup.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = True

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )

        self.outputs = outputs( self.id )

        self.register_run_length( 5.0 )


        env_vars = {}

        commandline = []

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        free_task.__init__( self, initial_state, no_reset )

class D(free_task):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/D.def

    name = 'D'
    short_name = 'D'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Combined post processing for the sea state and storm surge forecasts.',
    ]

    owner = None
    external_task = 'D.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        self.prerequisites.add( 'sea state fields ready for ' + self.c_time )
        self.prerequisites.add( 'storm surge fields ready for ' + self.c_time )

        self.outputs = outputs( self.id )

        self.register_run_length( 75.0 )

        self.outputs.add( 75.0, 'seagram products ready for ' + self.c_time )

        env_vars = {}

        commandline = []

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        free_task.__init__( self, initial_state, no_reset )

class C(forecast_model):
    # AUTO-GENERATED FROM /home/oliverh/cylc/systems/userguide2/taskdef/C.def

    name = 'C'
    short_name = 'C'
    instance_count = 0

    upward_instance_count = 0

    description = [
        'Could be a storm surge model, driving by the atmospheric model.',
        'Requires surface pressure and winds, and own restart file.',
        'Generates restart files for the next two cycles.',
    ]

    owner = None
    external_task = 'C.sh'

    remote_host = None
    valid_hours = [0,6,12,18]

    quick_death = False

    def __init__( self, c_time, initial_state, launcher, startup = False, no_reset = False ):

        # adjust cycle time to next valid for this task
        self.c_time = self.nearest_c_time( c_time )
        self.tag = self.c_time
        self.id = self.name + '%' + self.c_time
        hour = self.c_time[8:10]

        self.prerequisites = prerequisites( self.id )
        self.prerequisites.add( 'surface pressure field ready for ' + self.c_time )
        self.prerequisites.add( 'surface wind fields ready for ' + self.c_time )

        self.outputs = outputs( self.id )

        self.register_run_length( 120.0 )

        self.outputs.add( 118.0, 'storm surge fields ready for ' + self.c_time )

        env_vars = {}
        env_vars['NEXT_CYCLE_TIME'] = cycle_time.increment( self.c_time, 6)
        env_vars['NEXT_NEXT_CYCLE_TIME'] = cycle_time.increment( self.c_time, 12)

        commandline = []

        directives = {}

        params = {}
        params[ "env" ] = env_vars
        params[ "dir" ] = directives
        params[ "com" ] = commandline

        self.launcher = launcher
        launcher.configure( self.id, self.__class__.external_task, params, self.__class__.owner, self.__class__.remote_host )

        restart_times = [40.0,80.0]
        self.register_restarts( restart_times )

        forecast_model.__init__( self, initial_state, no_reset )

