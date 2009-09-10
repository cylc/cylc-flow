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
   
    # replace "$(MY_REFERENCE_TIME)"
    strng = re.sub( "^'\$\(MY_REFERENCE_TIME\)'$",   "self.ref_time",     strng ) # alone
    strng = re.sub( "^'\$\(MY_REFERENCE_TIME\)",     "self.ref_time + '", strng ) # start line
    strng = re.sub( "\$\(MY_REFERENCE_TIME\)'$", "' + self.ref_time"   ,  strng ) # end line
    strng = re.sub( "\$\(MY_REFERENCE_TIME\)" , "'  + self.ref_time + '", strng ) # mid line

    # replace "$(MY_REFERENCE_TIME - XX )"
    m = re.search( '\$\(\s*MY_REFERENCE_TIME\s*-\s*(\d+)\s*\)', strng )
    if m:
        strng = re.sub( "^'\$\(\s*MY_REFERENCE_TIME.*\)'$",   "reference_time.decrement( self.ref_time, " + m.group(1) + ")",     strng ) # alone
        strng = re.sub( "^'\$\(\s*MY_REFERENCE_TIME.*\)",     "reference_time.decrement( self.ref_time, " + m.group(1) + ") + '", strng ) # start line
        strng = re.sub( "\$\(\s*MY_REFERENCE_TIME.*\)'$", "' + reference_time.decrement( self.ref_time, " + m.group(1) + ")",     strng ) # mid line
        strng = re.sub( "\$\(\s*MY_REFERENCE_TIME.*\)",   "' + reference_time.decrement( self.ref_time, " + m.group(1) + ") + '", strng ) # end line

    # replace "$(MY_REFERENCE_TIME + XX )"
    m = re.search( '\$\(\s*MY_REFERENCE_TIME\s*\+\s*(\d+)\s*\)', strng )
    if m:
        strng = re.sub( "^'\$\(\s*MY_REFERENCE_TIME.*\)'$",   "reference_time.increment( self.ref_time, " + m.group(1) + ")",     strng ) # alone
        strng = re.sub( "^'\$\(\s*MY_REFERENCE_TIME.*\)",     "reference_time.increment( self.ref_time, " + m.group(1) + ") + '", strng ) # start line
        strng = re.sub( "\$\(\s*MY_REFERENCE_TIME.*\)'$", "' + reference_time.increment( self.ref_time, " + m.group(1) + ")",     strng ) # mid line
        strng = re.sub( "\$\(\s*MY_REFERENCE_TIME.*\)",   "' + reference_time.increment( self.ref_time, " + m.group(1) + ") + '", strng ) # end line

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
            'EXPORT', 'COTEMPORAL_DEPENDANTS_ONLY', 'PREREQUISITES',
            'STARTUP_PREREQUISITES', 'OUTPUTS', 'RUN_LENGTH_MINUTES',
            'TYPE', 'CONTACT_DELAY_HOURS', 'DESCRIPTION',
            'ONEOFF_FOLLOW_ON', 'RESTART_LIST_MINUTES' ]

    allowed_types = ['forecast_model', 'general_purpose' ]
    allowed_attributes = ['dummy', 'contact', 'sequential', 'oneoff' ]

    # open the output file
    FILE = open( task_class_file, 'w' )
    # python interpreter location
    FILE.write( '#!/usr/bin/python\n\n' )
    # auto-generation warning
    # preamble
    FILE.write( 
'''
from task_forecast import forecast_model
from task_general import general_purpose
from task_attributes import contact, oneoff, sequential, dummy 

import user_config            
import execution

import reference_time
from prerequisites import prerequisites
from prerequisites_fuzzy import fuzzy_prerequisites
from outputs import outputs
from time import sleep

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging
\n''')

    n_files = len(task_def_files)
    i = 0

    seen = {}

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

        # quick death (DEFAULT False)
        quick_death = False
        if 'COTEMPORAL_DEPENDANTS_ONLY' in parsed_def.keys():
            delayed_death = parsed_def[ 'COTEMPORAL_DEPENDANTS_ONLY' ][0]
            if delayed_death == 'True' or delayed_death == 'true' or delayed_death == 'Yes' or delayed_death == 'yes':
                quick_death = True

        if 'TYPE' not in parsed_def.keys():
            print "ERROR: no %TYPE specified"
            sys.exit(1)

        else:

            delay = 0
            fcmodel = False
            contact = False
            oneoff = False
            dummy = False
            sequential = False

            tmp = parsed_def[ 'TYPE' ][0]
            typelist = tmp.split(',')

            task_type = typelist[0]
            derived_from = task_type
            if task_type not in allowed_types:
                print 'ERROR, unknown task class:', task_type
                sys.exit(1)

            if task_type == 'forecast_model':
                fcmodel = True

            attributes = typelist[1:]
            if len(attributes) > 0:
                got_attributes = True

                # strip white space
                attributes = [ x.strip() for x in attributes ]

                for attribute in attributes:
                    if attribute not in allowed_attributes:
                        print 'ERROR, unknown task attribute:', attribute
                        print allowed_attributes
                        isys.exit(1)

                    if attribute == 'contact':
                        contact = True
                    elif attribute == 'dummy':
                        dummy = True
                    elif attribute == 'sequential':
                        sequential = True
                    elif attribute == 'oneoff':
                        oneoff = True

                # this assumes the order of attributes does not matter.
                derived_from = ','.join( attributes ) + ', ' + derived_from

        if 'EXTERNAL_TASK' in parsed_def.keys():
            external_task = parsed_def[ 'EXTERNAL_TASK' ][0]
            if dummy:
                print "WARNING: this task has the 'dummy' attribute; it will never use", external_task
        else:
            # no external task: dummy tasks only
            if not dummy:
                print 'ERROR: no external task specified'
                sys.exit(1)

        oneoff_follow_on = False
        if oneoff and not quick_death:
            if 'ONEOFF_FOLLOW_ON' not in parsed_def.keys():
                print "Error: oneoff tasks that have non-cotemporal dependants"
                print "must define %ONEOFF_FOLLOW_ON"
                sys.exit(1)
            else:
                oneoff_follow_on = parsed_def['ONEOFF_FOLLOW_ON'][0]

        task_init_def_args = 'ref_time, abdicated, initial_state'
        task_init_args = 'abdicated, initial_state'

        if contact:
            if 'CONTACT_DELAY_HOURS' not in parsed_def.keys():
                print "Error: contact classes must define %CONTACT_DELAY_HOURS"
                sys.exit(1)

            task_init_def_args += ", relative_state = 'catching_up'"
            contact_init_args = 'relative_state'

        if fcmodel:
            if 'RESTART_LIST_MINUTES' not in parsed_def.keys():
                print 'Error: forecast models must define %RESTART_LIST_MINUTES'
                sys.exit(1)
            else:
                restart_list = parsed_def[ 'RESTART_LIST_MINUTES' ][0]

        task_name = parsed_def[ 'NAME' ][0]

        if task_name in seen.keys():
            print "ERROR: task name '" + task_name + "' has been defined already!"
            sys.exit(1)
        else:
            seen[ task_name ] = True

        short_name = task_name
        m = re.search( '^\s*(.*),\s*(.*)\s*$', task_name )
        if m:
            # short name given as well
            [ task_name, short_name ] = m.groups()

        # class definition
        FILE.write( 'class ' + task_name + '(' + derived_from + '):\n' )

        indent_more()
 
        FILE.write( indent + '# AUTO-GENERATED FROM ' + task_def_file + '\n\n' )  
   
        # task name
        FILE.write( indent + 'name = \'' + task_name + '\'\n' )
        FILE.write( indent + 'short_name = \'' + short_name + '\'\n' )

        FILE.write( indent + 'instance_count = 0\n\n' )

        if contact:
            FILE.write( indent + 'catchup_mode = False\n\n' )

        # task description
        if 'DESCRIPTION' in parsed_def.keys():
            FILE.write( indent + 'description = [\n' )
            indent_more()
            for line in  parsed_def[ 'DESCRIPTION' ]:
                FILE.write( indent + "'" + line + "',\n" )
            indent_less()
            FILE.write( indent + ']\n\n' )
        else:
            print "ERROR: no %DESCRIPTION provided for task " + task_name
            sys.exit(1)

        # owner
        if 'OWNER' in parsed_def.keys():
            owner = parsed_def[ 'OWNER' ][0]
        else:
            # run as cyclon user
            owner = os.environ[ 'USER' ]
 
        FILE.write( indent + 'owner = \'' + owner + '\'\n' )

        # external task
        if not dummy:
            FILE.write( indent + 'external_task = \'' + external_task + '\'\n\n' )

        # valid hours
        FILE.write( indent + 'valid_hours = [' + parsed_def[ 'VALID_HOURS' ][0] + ']\n\n' )

        FILE.write( indent + 'quick_death = ' + str(quick_death) + '\n\n' )

        if oneoff_follow_on:
            FILE.write( indent + 'oneoff_follow_on = "' + oneoff_follow_on + '"\n\n' )

        # class init function
        FILE.write( indent + 'def __init__( self, ' + task_init_def_args + ' ):\n\n' )

        indent_more()

        FILE.write( indent + '# adjust reference time to next valid for this task\n' )
        FILE.write( indent + 'self.ref_time = self.nearest_ref_time( ref_time )\n' )
        FILE.write( indent + 'hour = self.ref_time[8:10]\n\n' )

        if contact:
            for line in parsed_def[ 'CONTACT_DELAY_HOURS' ]:
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

        # ... prerequisites
        FILE.write( indent + 'self.prerequisites = prerequisites( self.name, self.ref_time )\n' )
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
 

        # are the prerequisites different for the first instance?
        if 'STARTUP_PREREQUISITES' in parsed_def.keys():
            # TO DO: use a function to re-use the normal prerequisite
            # code (as above) here.
            FILE.write( '\n' + indent + "if self.ref_time == user_config.config['start_time']:\n" )
            FILE.write( indent + '# overwrite prerequisites for startup case\n' )
            indent_more()
                
            FILE.write( indent + 'self.prerequisites = prerequisites( self.name, self.ref_time )\n' )
            for line in parsed_def[ 'STARTUP_PREREQUISITES' ]:
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
 
            indent_less()

        # ... outputs
        FILE.write( '\n' )
        FILE.write( indent + 'self.outputs = outputs( self.name, self.ref_time )\n' )

        # automatic 'started' and 'finished' outputs
        if 'RUN_LENGTH_MINUTES' not in parsed_def:
            print "ERROR: %RUN_LENGTH_MINUTES not defined"
            sys.exit(1)

        FILE.write( '\n' )
        for line in parsed_def[ 'RUN_LENGTH_MINUTES' ]:
            line = re.sub( '\s+$', '', line )
            # look for conditionals
            m = re.match( '^([\d,]+)\s*\|\s*(.*)$', line )
            if m:
                [ left, rlen ] = m.groups()
                # get a list of hours
                hours = left.split(',')
                for hour in hours:
                    FILE.write( indent + 'if int( hour ) == ' + hour + ':\n' )
                    indent_more()
                    FILE.write( indent + 'self.register_run_length( ' + rlen + ' )\n' )
                    indent_less()
            else:
                rlen = line
                FILE.write( indent + 'self.register_run_length( ' + rlen + ' )\n\n' )
       
        if 'OUTPUTS' in parsed_def.keys():
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

        # environment variables
        strng = indent + 'self.env_vars = [\n'
        if 'EXPORT' in parsed_def.keys():
            for pair in parsed_def[ 'EXPORT' ]:
                [ var, val ] = pair.split( ' ', 1 )
                var = "'" + var + "'"
                # replace NAME and MY_REFERENCE_TIME variables
                val = interpolate_variables( "'" + val + "'" )
                strng = strng + indent + indent_unit + '[' + var + ', ' + val + '],\n' 

            strng = re.sub( ',\s*$', '', strng )
        strng = strng + ' ]\n\n' 
        FILE.write( strng )

        # forecast model restarts
        if fcmodel:
            FILE.write( indent + 'restart_times = [' + restart_list + ']\n' )
            FILE.write( indent + 'self.register_restarts( restart_times )\n\n' )

        # call parent init methods
        FILE.write( '\n' )
        if contact:
            FILE.write( indent + 'contact.__init__( self, ' + contact_init_args + ' )\n\n' )

        if dummy:
            FILE.write( indent + 'dummy.__init__( self )\n\n' )

        FILE.write( indent + task_type + '.__init__( self, ' + task_init_args + ' )\n\n' )


        #if 'EXPORT' in parsed_def.keys():
        #    # override run_external_task() for the export case
        #    indent_less()
        #    FILE.write( indent + 'def run_external_task( self, launcher ):\n' )
        #    FILE.write( indent + indent_unit + parent_class + '.run_external_task( self, launcher, self.env_vars )\n\n' )

        indent_less()
        indent_less()
 
    FILE.close()

if __name__ == '__main__':
    main( sys.argv )

