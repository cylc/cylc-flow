#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from task_types import daemon, asynchronous_task, forecast_model, free_task
from mod_oneoff import oneoff
from mod_sequential import sequential
from mod_contact import contact
from mod_catchup_contact import catchup_contact
from prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites_loose import loose_prerequisites
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
class watcher(daemon):

    name = 'watcher'
    short_name = 'watcher'
    instance_count = 0
    upward_instance_count = 0

    description = [
        'watch continuously for incoming satellite data',
    ]

    external_task = 'watcher.sh'

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False, no_reset = False ):

        # ignore c_time !!
        self.c_time = '2999010101'
        self.tag = str( self.__class__.upward_instance_count )
        self.id = self.name + '%' + self.tag

        #if startup:
        #    # overwrite prerequisites for startup case
        #    self.prerequisites = prerequisites( self.name, self.c_time )
        #    self.prerequisites.add( 'startup%'  + self.c_time + ' finished' )

        self.prerequisites = loose_prerequisites( self.name, self.c_time )

        self.outputs = outputs( self.name, self.c_time )
        self.output_pattern = 'pass (\w+) ready'
 
        self.env_vars = []

        # in dummy mode, replace the external task with _cylc-dummy-task
        #if dummy_mode:
        #        self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.get_identity(), self.external_task, self.env_vars )

        daemon.__init__( self, initial_state, no_reset )


class products(asynchronous_task):

    name = 'products'
    short_name = 'products'
    instance_count = 0
    upward_instance_count = 0

    description = [
        'process incoming satellite data',
    ]

    external_task = 'products.sh'

    def __init__( self, c_time, dummy_mode, initial_state, submit, startup = False, no_reset = False ):

        # ignore c_time !!
        self.c_time = '2999010101'
        self.tag = str( self.__class__.upward_instance_count )
        self.id = self.name + '%' + self.tag

        self.prerequisites = loose_prerequisites( self.name, self.c_time )
        self.prerequisites.add( 'pass (\w+) ready' )
        self.outputs = outputs( self.name, self.c_time )
        self.register_run_length( 60.0 )
        self.outputs.add( 60, 'products xxxx ready' )
 
        self.env_vars = []

        # in dummy mode, replace the external task with _cylc-dummy-task
        #if dummy_mode:
        #        self.external_task = '_cylc-dummy-task'

        modname = 'job_submit_methods'
        clsname = submit
        self.launcher = get_object( modname, clsname )( self.get_identity(), self.external_task, self.env_vars )

        asynchronous_task.__init__( self, initial_state, no_reset )
