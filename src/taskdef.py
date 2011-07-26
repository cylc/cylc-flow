#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

# NOT YET IMPLEMENTED OR DOCUMENTED FROM bin/_taskgen:
#   - time translation (for different units) not used
#   - not using the various check_() functions below
#   - asynch stuff, output_patterns

# ONEOFF and FOLLOWON TASKS: followon still needed but can now be
# identified automatically from the dependency graph?

# SUICIDE PREREQUISITES

import sys, re
from OrderedDict import OrderedDict

from prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites_loose import loose_prerequisites
from prerequisites import prerequisites
from plain_prerequisites import plain_prerequisites
from conditionals import conditional_prerequisites
from task_output_logs import logfiles
from collections import deque
from outputs import outputs
from dummy import dummy_command
from cycle_time import ct

class Error( Exception ):
    """base class for exceptions in this module."""
    pass

class DefinitionError( Error ):
    """
    Exception raise for errors in taskdef initialization.
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr( self.msg )

class taskdef(object):
    def __init__( self, name ):
        if re.search( '[^\w]', name ):
            raise DefinitionError, "ERROR: Illegal taskname: " + name
        self.name = name
        self.type = 'free'
        self.job_submit_method = 'background'
        self.job_submit_log_directory = None
        self.remote_cylc_directory = None
        self.remote_suite_directory = None
        self.remote_cylc_path = None
        self.manual_messaging = False
        self.modifiers = []

        self.owner = None
        self.remote_host = None

        self.hook_scripts = {}
        for event in [ 'submitted', 'submission failed', 'started', 
                'warning', 'succeeded', 'failed', 'timeout' ]:
            self.hook_scripts[ event ] = None

        self.timeouts = {}
        for item in [ 'submission', 'execution', 'reset on incoming' ]:
            self.timeouts[ item ] = None

        self.intercycle = False
        self.hours = []
        self.logfiles = []
        self.description = ['Task description has not been completed' ]

        self.members = []
        self.member_of = None
        self.follow_on_task = None

        self.clocktriggered_offset = None

        # triggers[0,6] = [ A, B:1, C(T-6), ... ]
        self.triggers = OrderedDict()         
        # cond[6,18] = [ '(A & B)|C', 'C | D | E', ... ]
        self.cond_triggers = OrderedDict()             
        self.startup_triggers = OrderedDict()
        self.suicide_triggers = OrderedDict()       
        self.asynchronous_triggers = []

        self.outputs = []     # list of special outputs; change to OrderedDict()
                              # if need to vary per cycle.

        self.output_patterns = []  # asynchronous daemon tasks

        self.loose_prerequisites = [] # asynchronous tasks
        self.death_prerequisites = [] # ditto

        # default to dummy task for tasks in graph but not in the [tasks] section.
        self.commands = [ dummy_command ] # list of commands
        self.environment = OrderedDict()  # var = value
        self.directives  = OrderedDict()  # var = value

    def add_trigger( self, msg, cycle_list_string ):
        if cycle_list_string not in self.triggers:
            self.triggers[ cycle_list_string ] = []
        self.triggers[ cycle_list_string ].append( msg )

    def add_asynchronous_trigger( self, msg ):
        self.asynchronous_triggers.append( msg )

    def add_startup_trigger( self, msg, cycle_list_string ):
        if cycle_list_string not in self.startup_triggers:
            self.startup_triggers[ cycle_list_string ] = []
        self.startup_triggers[ cycle_list_string ].append( msg )

    def add_conditional_trigger( self, triggers, exp, cycle_list_string ):
        # triggers[label] = trigger
        # expression relates the labels
        if cycle_list_string not in self.cond_triggers:
            self.cond_triggers[ cycle_list_string ] = []
        self.cond_triggers[ cycle_list_string ].append( [ triggers, exp ] )

    def add_hours( self, section_label ):
        # list of valid hours
        hours = re.split( '\s*,\s*', section_label )
        for hr in hours:
            hour = int( hr )
            if hour < 0 or hour > 23:
                raise DefinitionError( 'ERROR: Hour ' + str(hour) + ' must be between 0 and 23' )
            if hour not in self.hours: 
                self.hours.append( hour )
            self.hours.sort( key=int )

    def add_asynchid( self, asyncid ):
        self.output_patterns.append( asyncid )

    def check_consistency( self ):
        if len( self.hours ) == 0:
            raise DefinitionError( 'ERROR: no hours specified' )

        if 'clocktriggered' in self.modifiers:
            if self.clocktriggered_offset == None:
                raise DefinitionError( 'ERROR: clock-triggered tasks must specify a time offset' )

        if self.member_of and len( self.members ) > 0:
            raise DefinitionError( 'ERROR: nested task families are not allowed' )

    def time_trans( self, strng, hours=False ):
        # translate a time of the form:
        #  x sec, y min, z hr
        # into float MINUTES or HOURS,
    
        if not re.search( '^\s*(.*)\s*min\s*$', strng ) and \
            not re.search( '^\s*(.*)\s*sec\s*$', strng ) and \
            not re.search( '^\s*(.*)\s*hr\s*$', strng ):
                print >> sys.stderr, "ERROR: missing time unit on " + strng
                sys.exit(1)
    
        m = re.search( '^\s*(.*)\s*min\s*$', strng )
        if m:
            [ mins ] = m.groups()
            if hours:
                return str( float( mins / 60.0 ) )
            else:
                return str( float(mins) )
    
        m = re.search( '^\s*(.*)\s*sec\s*$', strng )
        if m:
            [ secs ] = m.groups()
            if hours:
                return str( float(secs)/3600.0 )
            else:
                return str( float(secs)/60.0 )
    
        m = re.search( '^\s*(.*)\s*hr\s*$', strng )
        if m:
            [ hrs ] = m.groups()
            if hours:
                #return str( float(hrs) )
                return float(hrs)
            else:
                #return str( float(hrs)*60.0 )
                return float(hrs)*60.0

    def get_task_class( self ):
        # return a task proxy class definition, to be used for
        # instantiating objects of this particular task class.
        base_types = []
        for foo in self.modifiers + [self.type]:
            mod = __import__( foo )
            base_types.append( getattr( mod, foo ) )

        tclass = type( self.name, tuple( base_types), dict())
        tclass.name = self.name        # TO DO: NOT NEEDED, USED class.__name__
        tclass.instance_count = 0
        tclass.upward_instance_count = 0
        tclass.description = self.description

        tclass.elapsed_times = []
        tclass.mean_total_elapsed_time = None

        tclass.owner = self.owner

        tclass.timeouts = self.timeouts

        tclass.hook_scripts = self.hook_scripts
        tclass.remote_host = self.remote_host

        # TO DO: can this be moved into task base class?
        tclass.job_submit_method = self.job_submit_method
        tclass.job_submit_log_directory = self.job_submit_log_directory
        tclass.remote_cylc_directory = self.remote_cylc_directory
        tclass.remote_suite_directory = self.remote_suite_directory
        tclass.manual_messaging = self.manual_messaging

        tclass.valid_hours = self.hours

        tclass.intercycle = self.intercycle
        tclass.follow_on = self.follow_on_task

        if self.type == 'family':
            tclass.members = self.members

        if self.member_of:
            tclass.member_of = self.member_of

        def tclass_format_asynchronous_prerequisites( sself, preq ):
            m = re.search( '\$\(TAG\s*\-\s*(\d+)\)', preq )
            if m:
                offset = m.groups()[0]
                foo = sself.tag - offset
                preq = re.sub( '\$\(TAG\s*\-\s*\d+\)', foo, preq )
            else:
                preq = re.sub( '\$\(TAG\)', sself.tag, preq )
            return preq
        tclass.format_asynchronous_prerequisites = tclass_format_asynchronous_prerequisites 

        def tclass_format_prerequisites( sself, preq ):
            m = re.search( '\$\(CYCLE_TIME\s*\-\s*(\d+)\)', preq )
            if m:
                offset = m.groups()[0]
                foo = ct( sself.c_time )
                foo.decrement( hours=offset )
                ctime = foo.get()
                preq = re.sub( '\$\(CYCLE_TIME\s*\-\s*\d+\)', ctime, preq )
            else:
                preq = re.sub( '\$\(CYCLE_TIME\)', sself.tag, preq )
            return preq
        tclass.format_prerequisites = tclass_format_prerequisites 

        def tclass_add_prerequisites( sself, startup ):

            pp = plain_prerequisites( sself.id ) 
            # if startup, use ONLY startup prerequisites
            # IF THERE ARE ANY
            if startup:
                found = False
                for cycles in self.startup_triggers:
                    trigs = self.startup_triggers[ cycles ]
                    hours = re.split( ',\s*', cycles )
                    for hr in hours:
                        if int( sself.c_hour ) == int( hr ):
                            for trig in trigs:
                                found = True
                                pp.add( sself.format_prerequisites( trig ))
                if found:
                    sself.prerequisites.add_requisites( pp )

            pp = plain_prerequisites( sself.id ) 
            for cycles in self.triggers:
                trigs = self.triggers[ cycles ]
                hours = re.split( ',\s*', cycles )
                for hr in hours:
                    if int( sself.c_hour ) == int( hr ):
                        for trig in trigs:
                            pp.add( sself.format_prerequisites( trig ))
            sself.prerequisites.add_requisites( pp )

            # conditional triggers
            for cycles in self.cond_triggers:
                for ctrig in self.cond_triggers[ cycles ]:
                    triggers, exp =  ctrig
                    hours = re.split( ',\s*', cycles )
                    for hr in hours:
                        if int( sself.c_hour ) == int( hr ):
                            cp = conditional_prerequisites( sself.id )
                            for label in triggers:
                                trig = triggers[label]
                                cp.add( sself.format_prerequisites( trig ), label )
                            cp.set_condition( exp )
                            sself.prerequisites.add_requisites( cp )

            if self.type == 'asynchronous' or self.type == 'sas':
                sself.death_prerequisites = plain_prerequisites(sself.id)
                for pre in self.death_prerequisites:
                    sself.death_prerequisites.add( sself.format_asynchronous_prerequisites( pre ))

            if len( self.loose_prerequisites ) > 0:
                lp = loose_prerequisites(sself.id)
                for pre in self.loose_prerequisites:
                    lp.add( pre )
                sself.prerequisites.add_requisites( lp )

            if len( self.asynchronous_triggers ) > 0:
                pp = plain_prerequisites( sself.id ) 
                for trigger in self.asynchronous_triggers:
                    pp.add( sself.format_asynchronous_prerequisites( trigger ))
                sself.prerequisites.add_requisites( pp )

        tclass.add_prerequisites = tclass_add_prerequisites

        # class init function
        def tclass_init( sself, start_c_time, initial_state, stop_c_time=None, startup=False ):
            sself.tag = sself.adjust_tag( start_c_time )
            if self.type != 'asynchronous' and self.type != 'daemon' and self.type != 'sas':
                sself.c_time = sself.tag
                sself.c_hour = sself.c_time[8:10]
                sself.orig_c_hour = start_c_time[8:10]
 
            sself.id = sself.name + '%' + sself.tag
            sself.external_tasks = deque()

            for command in self.commands:
                sself.external_tasks.append( command )
 
            if 'clocktriggered' in self.modifiers:
                sself.real_time_delay =  float( self.clocktriggered_offset )

            sself.output_patterns = self.output_patterns

            # prerequisites
            sself.prerequisites = prerequisites()
            sself.add_prerequisites( startup )

            ## should these be conditional too:?
            sself.suicide_prerequisites = plain_prerequisites( sself.id )
            ##sself.add_requisites( sself.suicide_prerequisites, self.suicide_triggers )

            # TO DO: UPDATE FAMILIES FOR ASYNCHRONOUS TASKS? (c_time below)
            if self.member_of:
                foo = plain_prerequisites( sself.id )
                foo.add( self.member_of + '%' + sself.c_time + ' started' )
                sself.prerequisites.add_requisites( foo )

            if self.type == 'family':
                # familysucceeded prerequisites (all satisfied => all
                # members finished successfully).
                sself.familysucceeded_prerequisites = plain_prerequisites( sself.id )
                for member in self.members:
                    sself.familysucceeded_prerequisites.add( member + '%' + sself.c_time + ' succeeded' )
                # familyOR prerequisites (A|A:fail and B|B:fail and ...)
                # all satisfied => all members have either succeeded or failed.
                sself.familyOR_prerequisites = conditional_prerequisites( sself.id )
                expr = ''
                for member in self.members:
                    expr += '( ' + member + ' | ' + member + '_fail ) & '
                    sself.familyOR_prerequisites.add( member + '%' + sself.c_time + ' succeeded', member )
                    sself.familyOR_prerequisites.add( member + '%' + sself.c_time + ' failed', member + '_fail' )
                sself.familyOR_prerequisites.set_condition( expr.rstrip('& ') )

            sself.logfiles = logfiles()
            for lfile in self.logfiles:
                sself.logfiles.add_path( lfile )

            # outputs
            sself.outputs = outputs( sself.id )
            for output in self.outputs:
                m = re.search( '\$\(CYCLE_TIME\s*([+-])\s*(\d+)\)', output )
                if m:
                    sign, offset = m.groups()
                    if sign == '-':
                       raise DefinitionError, "ERROR, " + sself.id + ": Output offsets must be positive: " + output
                    else:
                        #ctime = cycle_time.increment( sself.c_time, offset )
                        foo = ct( sself.c_time )
                        foo.increment( hours=offset )
                        ctime = foo.get()
                    out = re.sub( '\$\(CYCLE_TIME.*\)', ctime, output )
                elif re.search( '\$\(CYCLE_TIME\)', output ):
                    out = re.sub( '\$\(CYCLE_TIME\)', sself.tag, output )
                else:
                    out = output
                sself.outputs.add( out )
            sself.outputs.register()

            sself.env_vars = OrderedDict()
            for var in self.environment:
                val = self.environment[ var ]
                sself.env_vars[ var ] = val

            sself.directives = OrderedDict()
            for var in self.directives:
                val = self.directives[ var ]
                sself.directives[ var ] = val

            if 'catchup_clocktriggered' in self.modifiers:
                catchup_clocktriggered.__init__( sself )
 
            if stop_c_time:
                # cycling tasks with a final cycle time set
                super( sself.__class__, sself ).__init__( initial_state, stop_c_time ) 
            else:
                # TO DO: TEMPORARY HACK FOR ASYNC
                sself.stop_c_time = '9999123123'
                super( sself.__class__, sself ).__init__( initial_state ) 

        tclass.__init__ = tclass_init

        return tclass
