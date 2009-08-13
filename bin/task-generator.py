#!/usr/bin/python

import string
import glob
import sys
import re

import os
#print os.getcwd()

def usage():
    print 'USAGE: ' + sys.argv[0] + ' <list of task definition files>'
    sys.exit(1)

def indent_more():
    global indent
    global indent_unit
    indent += indent_unit

def indent_less():
    global indent
    global indent_unit
    indent = re.sub( indent_unit, '', indent, 1 )
    
def print_parsed_info():

    global parsed_def

    for k in parsed_def.keys():
        print
        print k + ':' 
        for val in parsed_def[ k ]:
            print ' - ' + val

def interpolate_variables( strng ):
    # interpolate taskdef variables in a string

    # strng = "'a string'"  (SINGLE QUOTES REQUIRED)

    # strip leading spaces
    strng = re.sub( "^'\s+", "'", strng )

    # replace $(NAME) with self.name
    strng = re.sub( "^'\$\(NAME\)'$",   "self.name",     strng ) # alone
    strng = re.sub( "^'\$\(NAME\)",     "self.name + '", strng ) # start line
    strng = re.sub( "\$\(NAME\)'$", "' + self.name"   ,  strng ) # end line
    strng = re.sub( "\$\(NAME\)" , "'  + self.name + '", strng ) # mid line
   
    # replace "$(MY_REFERENCE_TIME)" or "$(MY_REFERENCE_TIME - XX )"
    m = re.search( '\$\(\s*MY_REFERENCE_TIME\s*-\s*(\d+)\s*\)', strng )
    if not m:
        # straight
        strng = re.sub( "^'\$\(MY_REFERENCE_TIME\)'$",   "ref_time",     strng ) # alone
        strng = re.sub( "^'\$\(MY_REFERENCE_TIME\)",     "ref_time + '", strng ) # start line
        strng = re.sub( "\$\(MY_REFERENCE_TIME\)'$", "' + ref_time"   ,  strng ) # end line
        strng = re.sub( "\$\(MY_REFERENCE_TIME\)" , "'  + ref_time + '", strng ) # mid line
    else:
        # arithmetic
        strng = re.sub( "^'\$\(\s*MY_REFERENCE_TIME.*\)'$",   "reference_time.decrement( ref_time, " + m.group(1) + ")",     strng ) # alone
        strng = re.sub( "^'\$\(\s*MY_REFERENCE_TIME.*\)",     "reference_time.decrement( ref_time, " + m.group(1) + ") + '", strng ) # start line
        strng = re.sub( "\$\(\s*MY_REFERENCE_TIME.*\)'$", "' + reference_time.decrement( ref_time, " + m.group(1) + ")",     strng ) # mid line
        strng = re.sub( "\$\(\s*MY_REFERENCE_TIME.*\)",   "' + reference_time.decrement( ref_time, " + m.group(1) + ") + '", strng ) # end line

    return strng

#================= MAIN PROGRAM ========================================
def main( argv ):

    global parsed_def
    global FILE

    global indent, indent_unit
    indent = ''
    indent_unit = '    '

    task_class_file = 'task_classes.py'

    if len( argv ) < 2:
        usage()

    task_def_files = argv[1:]

    allowed_keys = [ 'NAME', 'OWNER', 'VALID_HOURS', 'EXTERNAL_TASK',
            'EXPORT', 'DELAYED_DEATH', 'PREREQUISITES', 'OUTPUTS',
            'RUN_LENGTH_MINUTES', 'TYPE', 'DELAY_HOURS', 'UPSTREAM' ]

    # open the output file
    FILE = open( task_class_file, 'w' )
    # python interpreter location
    FILE.write( '#!/usr/bin/python\n\n' )
    # auto-generation warning
    # preamble
    FILE.write( 
'''
from task import sequential_task, parallel_task, sequential_contact_task, parallel_contact_task
import execution

import reference_time
from requisites import prerequisites, outputs, fuzzy_prerequisites
from time import sleep

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging
\n''')

    n_files = len(task_def_files)
    i = 0

    for task_def_file in task_def_files:

        i = i + 1

        DEF = open( task_def_file, 'r' )
        lines = DEF.readlines()
        DEF.close()

        print '  + ' + task_def_file

        if re.match( '^.*\.py$', task_def_file ):
            # this file is a python class definition
            for line in lines:
                FILE.write( line )

            FILE.write( '\n' )
            continue

        current_key = None

        parsed_def = {}
        for lline in lines:

            line = string.strip( lline )

            # skip blank lines
            if re.match( '^\s*$', line ):
                continue

            # skip comment lines
            if re.match( '^\s*#.*', line ):
                continue

            if re.match( '^%.*', line ):
                # new key identified
                current_key = string.lstrip( line, '%' )
                # print 'new key: ' + current_key,
                if current_key not in allowed_keys:
                    print 'ILLEGAL KEY ERROR: ' + current_key
                    sys.exit(1)
                parsed_def[ current_key ] = []

            else:
                if current_key == None:
                    # can this ever happen?
                    print "Error: no key identified"
                    sys.exit(1)
    
                # data associated with current key
                parsed_def[ current_key ].append( line ) 

        # print_parsed_info()

        # defaults
        parent_class = 'task'
        type = 'sequential'
        delay = 0
        contact = False
        if 'TYPE' in parsed_def.keys():
            type = parsed_def[ 'TYPE' ][0]
            if type == 'sequential':
                parent_class = 'sequential_task'

            elif type == 'parallel':
                parent_class = 'parallel_task'

            elif re.match( 'sequential,\s*contact', type ):
                contact = True
                parent_class = 'sequential_contact_task'

            elif re.match( 'parallel,\s*contact', type ):
                contact = True
                parent_class = 'parallel_contact_task'

        else:
            print "Error: no %TYPE specified"
            sys.exit(1)

        def_init_args = 'ref_time, abdicated, initial_state'
        par_init_args = 'ref_time, abdicated, initial_state'
        if contact:
            if 'DELAY_HOURS' not in parsed_def.keys():
                print "Error: contact classes must define %DELAY_HOURS"
                sys.exit(1)

            def_init_args = "ref_time, abdicated, initial_state, relative_state = 'catching_up'"
            par_init_args = "ref_time, abdicated, initial_state, relative_state"

        task_name = parsed_def[ 'NAME' ][0]
        short_name = task_name
        m = re.search( '^\s*(.*),\s*(.*)\s*$', task_name )
        if m:
            # short name given as well
            [ task_name, short_name ] = m.groups()

        # class definition
        FILE.write( 'class ' + task_name + '(' + parent_class + '):\n' )

        indent_more()
 
        FILE.write( indent + '# AUTO-GENERATED FROM ' + task_def_file + '\n\n' )  
   
        # task name
        FILE.write( indent + 'name = \'' + task_name + '\'\n' )
        FILE.write( indent + 'short_name = \'' + short_name + '\'\n' )

        FILE.write( indent + 'instance_count = 0\n\n' )

        # owner
        if 'OWNER' in parsed_def.keys():
            owner = parsed_def[ 'OWNER' ][0]
        else:
            # run as cyclon user
            owner = os.environ[ 'USER' ]
 
        FILE.write( indent + 'owner = \'' + owner + '\'\n' )

        # external task
        FILE.write( indent + 'external_task = \'' + parsed_def[ 'EXTERNAL_TASK' ][0] + '\'\n\n' )
        # valid hours
        FILE.write( indent + 'valid_hours = [' + parsed_def[ 'VALID_HOURS' ][0] + ']\n\n' )

        # quick death? (DEFAULT False)
        quick_death = 'True'
        if 'DELAYED_DEATH' in parsed_def.keys():
            delayed_death = parsed_def[ 'DELAYED_DEATH' ][0]
            if delayed_death == 'True' or delayed_death == 'true' or delayed_death == 'Yes' or delayed_death == 'yes':
                quick_death = 'False'

            FILE.write( indent + 'quick_death = ' + quick_death + '\n\n' )

        # class init function
        FILE.write( indent + 'def __init__( self, ' + def_init_args + ' ):\n\n' )

        indent_more()

        FILE.write( indent + '# adjust reference time to next valid for this task\n' )
        FILE.write( indent + 'ref_time = self.nearest_ref_time( ref_time )\n' )
        FILE.write( indent + 'hour = ref_time[8:10]\n\n' )

        if contact:
            for line in parsed_def[ 'DELAY_HOURS' ]:
                # look for conditionals
                m = re.match( '^([\d,]+)\s*\|\s*(.*)$', line )
                if m:
                    [ left, delay ] = m.groups()
                    # get a list of hours
                    hours = left.split(',')
                    for hour in hours:
                        FILE.write( indent + 'if int( hour ) == ' + hour + ':\n' )
                        indent_more()
                        FILE.write( indent + 'self.real_time_delay = ' + str( delay ) + '\n' )
                        indent_less()
                else:
                    FILE.write( indent + 'self.real_time_delay = ' + str( line ) + '\n' )

            FILE.write( '\n' )

        # extra environment variables
        if 'EXPORT' in parsed_def.keys():
            strng = indent + 'self.env_vars = [\n'
            for pair in parsed_def[ 'EXPORT' ]:
                [ var, val ] = pair.split( ' ', 1 )
                var = "'" + var + "'"
                # replace NAME and MY_REFERENCE_TIME variables
                val = interpolate_variables( "'" + val + "'" )
                strng = strng + indent + indent_unit + '[' + var + ', ' + val + '],\n' 

            strng = re.sub( ',\s*$', '', strng )
            strng = strng + ' ]\n\n' 
            FILE.write( strng )

        # ... prerequisites
        FILE.write( indent + 'self.prerequisites = prerequisites( self.name, ref_time )\n' )
        for line in parsed_def[ 'PREREQUISITES' ]:
            # look for conditionals
            m = re.match( '^([\d,]+)\s*\|\s*(.*)$', line )
            if m:
                [ left, req ] = m.groups()
                # get a list of hours
                hours = left.split(',')
                req = re.sub( '^\s+', '', req )
                req = "'" + req + "'"
                req = interpolate_variables( req )
                for hour in hours:
                    FILE.write( indent + 'if int( hour ) == ' + hour + ':\n' )
                    indent_more()
                    FILE.write( indent + 'self.prerequisites.add( ' + req + ' )\n' )
                    indent_less()
            else:
                req = "'" + line + "'"
                req = interpolate_variables( req )
                FILE.write( indent + 'self.prerequisites.add( ' + req + ' )\n' )
 

        # ... outputs
        FILE.write( '\n' )
        FILE.write( indent + 'self.outputs = outputs( self.name, ref_time )\n' )

        # automatic 'task started' message
        parsed_def[ 'OUTPUTS' ].append( '0: $(NAME) started for $(MY_REFERENCE_TIME)' )
    
        # automatic 'task finished' message
        for line in parsed_def[ 'RUN_LENGTH_MINUTES' ]:
            line = re.sub( '\s+$', '', line )
            parsed_def[ 'OUTPUTS' ].append( line + ': $(NAME) finished for $(MY_REFERENCE_TIME)' )
        
        for line in parsed_def[ 'OUTPUTS' ]:
            # look for conditionals
            m = re.match( '^([\d,]+)\s*\|\s*(.*)$', line )
            if m:
                [ left, timed_req ] = m.groups()
                # get a list of hours
                hours = left.split(',')
                [ time, req ] = timed_req.split( ':' )
                req = "'" + req + "'"
                req = interpolate_variables( req )
                for hour in hours:
                    FILE.write( indent + 'if int( hour ) == ' + hour + ':\n' )
                    indent_more()
                    FILE.write( indent + 'self.outputs.add( ' + time + ', ' + req + ' )\n' )
                    indent_less()
            else:
                timed_req = line
                [ time, req ] = timed_req.split( ':' )
                req = "'" + req + "'"
                req = interpolate_variables( req )
                FILE.write( indent + 'self.outputs.add( ' + time + ', ' + req + ' )\n' )

        # call parent's init method
        FILE.write( '\n' )
        FILE.write( indent + parent_class + '.__init__( self, ' + par_init_args + ' )\n\n' )


        if 'UPSTREAM' in parsed_def.keys():
            # override get_cutoff()
            indent_less()
            FILE.write( indent + 'def get_cutoff( self, finished_task_dict ):\n' )
            indent_more()
            FILE.write( indent + '# set cutoff to most recent finished ' + parsed_def[ 'UPSTREAM' ][0] + '\n\n' )
            FILE.write( indent + "if self.state == 'waiting' or ( self.state == 'running' and not self.abdicated ) or ( self.state == 'finished' and not self.abdicated ):\n" )
            indent_more()

            FILE.write( indent + 'cutoff = self.ref_time\n' )
            FILE.write( indent + 'ref_times = []\n' )
            FILE.write( indent + 'if "' + parsed_def[ 'UPSTREAM' ][0] + '" in finished_task_dict.keys():\n' )
            indent_more()
            FILE.write( indent + 'ref_times = finished_task_dict[ "' + parsed_def[ 'UPSTREAM' ][0] + '" ]\n' )

            FILE.write( indent + "ref_times.sort( key = int, reverse = True )\n" + \
                    indent + "for rt in ref_times:\n" )
            indent_more()
            FILE.write( indent + "if int( rt ) <= int( self.ref_time ):\n" )
            indent_more()
            FILE.write( indent + "cutoff = rt\n" + indent + "break\n" )
            indent_less()
            indent_less()
            indent_less()
            indent_less()
            FILE.write( indent + "else:\n" )
            indent_more()
            FILE.write( indent + "cutoff = None\n\n" )
            indent_less()
            FILE.write( indent + "return cutoff\n\n\n" )


        if 'EXPORT' in parsed_def.keys():
            # override run_external_task() for the export case
            indent_less()
            FILE.write( indent + 'def run_external_task( self, launcher ):\n' )
            FILE.write( indent + indent_unit + parent_class + '.run_external_task( self, launcher, self.env_vars )\n\n' )

        indent_less()
        indent_less()
 
    FILE.close()

if __name__ == '__main__':
    main( sys.argv )

