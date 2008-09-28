#!/usr/bin/python

"""
Class to maintain "task configuration" information: it supplies a list
of tasks that should be created for a given reference time. 

By default get_config() returns all tasks for any reference time.

Otherwise a task config file can be supplied at initialisation. 
This defines the task list for a set of transitional reference times:
   config[ YYYYMMDDHH ] = [ task list ]
After each configured transitional time the status quo is maintained
until the next transitional time, if any, is reached. 
"""

from task_definitions import all_task_names

import re

class task_config:

    """
    config[ reference_time.to_str() ] = [list of configured task names]
    for transitional reference times (status quo at other times)
    """

    def __init__( self, filename ):

        self.config = {}
        if filename is not None:
            self.parse_file( filename )


    def parse_file( self, filename ):

        print
        print "Parsing Task Config File ..."

        config = {}

        cfile = open( filename, 'r' )
        for line in cfile:

            # skip full line comments
            if re.compile( "^#" ).match( line ):
                continue

            # skip blank lines
            if re.compile( "^\s*$" ).match( line ):
                continue

            print " + ", line,

            # line format: "YYYYMMDDHH task1 task2 task3:finished [etc.]"
            tokens = line.split()
            ref_time = tokens[0]  # could use reference_time class here to check validity
            the_rest = tokens[1:]

            # check tasks are known
            for taskx in the_rest:
                task = taskx
                if re.compile( "^.*:").match( taskx ):
                    task = taskx.split(':')[0]

                if not task in all_task_names:
                    if task != "stop" and task != "all":
                        print "ERROR: unknown task ", task
                        sys.exit(1)

            # add task list to the dict
            self.config[ ref_time ] = the_rest

        cfile.close()

    def get_ordered_keys( self ):

        # get REVERSE ordered list of configured reference times 
        tmp = {}
        for rt in self.config.keys():
            i_rt = int( rt )
            tmp[ i_rt ] = rt

        ordered = []

        o_i_rt = sorted( tmp.keys(), reverse = True )
        for rt in o_i_rt:
            ordered.append( tmp[ rt ] )

        return ordered

    def get_config( self, ref_time ):

        list = all_task_names

        ordered_transitional_times = self.get_ordered_keys()

        if len( ordered_transitional_times ) > 0:
            if int( ref_time ) < int( ordered_transitional_times[-1] ):
                print
                print "WARNING: requested reference time (" + ref_time + ") is EARLIER than"
                print "         first configured reference time (" + ordered_transitional_times[-1] + ")."
                print "         I will instantiate ALL tasks for this reference time."
                print

        for rt in ordered_transitional_times:
            if int( ref_time ) >= int( rt ):
               list = self.config[ rt ]
               break
       
        if list[0] == 'all':
            list = all_task_names

        if list[0] == 'stop':
            list = []

        return list
