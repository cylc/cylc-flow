#!/usr/bin/python

# cylon user configuration file
# see config.py for options

# DO NOT REMOVE THESE LINES          # !
import logging  # for logging level  # !
import os       # os.environ['HOME'] # !
# config[ 'item_name' ] = item_value # !
config = {}                          # !
config[ 'task_groups' ] = {}         # !

config[ 'system_name' ] = 'scs-demo'
config[ 'use_qsub' ] = False
config[ 'logging_dir' ]     = 'LOG'
config[ 'state_dump_file' ] = 'STATE/state'

config[ 'task_list' ] = \
        [
            'g_lbc_cold',
            'UM_cold',
            'g_gbl_cold',
            'g_bge',
            'g_lbc',
            'g_obs',
            'post',
            #'post2',
            'arch',
            'VAR',
            'UM_nz',
            'OPS1',
            'OPS2',
            'OPS3'
        ]

config[ 'task_groups' ][ 'coldstart' ] = \
        [ 
            'UM_cold', 
            'g_lbc_cold', 
            'g_gbl_cold' 
        ]

