#!/usr/bin/python

"""
Class to parse an EcoConnect controller config file and handle task
creation according to the resulting configuration parameters (lists of
task names for particular transitional reference times).
"""

from reference_time import reference_time
from vtasks_dummy import *
import re
import sys

class vtask_config:

    all_tasks = [ 'A', 'B', 'C', 'D', 'E', 'F', 'G' ]

    def __init__( self, filename = None ):

        self.ordered_ref_times = []
        self.task_lists = {}

        if filename is None:
            self.config_supplied = False
            return

        self.config_supplied = True
        cfile = open( filename, 'r' )

        for line in cfile:

            # skip full line comments
            if re.compile( "^#" ).match( line ):
                continue

            # skip blank lines
            if re.compile( "^\s*$" ).match( line ):
                continue

            # line format: "YYYYMMDDHH [task list]"
            tokens = line.split()
            ref_time = reference_time( tokens[0] )
            foo = tokens[1:]

            # check tasks are known
            for task in foo:
                if not task in vtask_config.all_tasks:
                    if task != "stop" and task != "all":
                        print "ERROR: unknown task ", task
                        sys.exit(1)

            # add to task_list dict
            self.task_lists[ ref_time ] = foo


        # get ordered list of keys for the dict
        tmp = {}
        for rt in self.task_lists.keys():
            i_rt = rt.to_int() 
            tmp[ i_rt ] = rt

        o_i_rt = sorted( tmp.keys(), reverse = True )
        for rt in o_i_rt:
            self.ordered_ref_times.append( tmp[ rt ] )


    def create_tasks( self, reference_time ):

        if not self.config_supplied:
            in_utero = vtask_config.all_tasks

        else:

            if reference_time.is_lessthan( self.ordered_ref_times[-1] ):
                print
                print "WARNING: current reference time (" + reference_time.to_str() + ") is EARLIER than"
                print "         first configured reference time (" + self.ordered_ref_times[-1].to_str() + "). I will"
                print "         instantiate ALL tasks for this reference time."
                print
                in_utero = vtask_config.all_tasks

            for rt in self.ordered_ref_times:
                 if reference_time.is_greaterthan_or_equalto( rt ):
                     in_utero = self.task_lists[ rt ]
                     break

        if in_utero[0] == 'all':
            in_utero = vtask_config.all_tasks

        if in_utero[0] == 'stop':
            print "Warning: stop requested for", reference_time.to_str()
            in_utero = []

        birth = []
        for task in in_utero:
            if task == 'A':
                birth.append( A( reference_time )) 
            elif task == 'B':
                birth.append( B( reference_time ))
            elif task == 'C':
                birth.append( C( reference_time ))
            elif task == 'D':
                birth.append( D( reference_time )) 
            elif task == 'E':
                birth.append( E( reference_time )) 
            elif task == 'F':
                birth.append( F( reference_time ))
            elif task == 'G':
                birth.append( G( reference_time ))
            else:
                print "ERROR: unknown task", task

        return birth
