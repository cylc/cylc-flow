#!/usr/bin/env python

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
from prerequisites import prerequisites
from plain_prerequisites import plain_prerequisites
from conditionals import conditional_prerequisites
from task_output_logs import logfiles
from collections import deque
from outputs import outputs
from dummy import dummy_command
import cycle_time

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
        self.modifiers = []

        self.owner = None
        self.host = None

        self.execution_timeout_minutes = None
        self.reset_execution_timeout_on_incoming_messages = True
        self.task_submitted_hook = None
        self.task_started_hook = None
        self.task_finished_hook = None
        self.task_failed_hook = None
        self.task_warning_hook = None
        self.task_submission_failed_hook = None
        self.task_timeout_hook = None

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

        self.outputs = []     # list of special outputs; change to OrderedDict()
                              # if need to vary per cycle.

        # default to dummy task for tasks in graph but not in the [tasks] section.
        self.commands = [ dummy_command ] # list of commands
        self.pre_scripting  = ''          # list of lines
        self.post_scripting = ''          # list of lines
        self.environment = OrderedDict()  # var = value
        self.directives  = OrderedDict()  # var = value

    def add_trigger( self, msg, cycle_list_string ):
        if cycle_list_string not in self.triggers:
            self.triggers[ cycle_list_string ] = []
        self.triggers[ cycle_list_string ].append( msg )

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

    def add_hours( self, hours ):
        for hr in hours:
            hour = int( hr )
            if hour < 0 or hour > 23:
                raise DefinitionError( 'ERROR: Hour ' + str(hour) + ' must be between 0 and 23' )
            if hour not in self.hours: 
                self.hours.append( hour )
            self.hours.sort( key=int )

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
                print "ERROR: missing time unit on " + strng
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

        #print self.name, base_types

        tclass = type( self.name, tuple( base_types), dict())
        tclass.name = self.name        # TO DO: NOT NEEDED, USED class.__name__
        tclass.instance_count = 0
        tclass.description = self.description

        tclass.elapsed_times = []
        tclass.mean_total_elapsed_time = None

        tclass.owner = self.owner

        tclass.execution_timeout_minutes = self.execution_timeout_minutes

        tclass.reset_execution_timeout_on_incoming_messages = self.reset_execution_timeout_on_incoming_messages

        tclass.task_submitted_hook = self.task_submitted_hook
        tclass.task_started_hook = self.task_started_hook
        tclass.task_finished_hook = self.task_finished_hook
        tclass.task_failed_hook = self.task_failed_hook
        tclass.task_warning_hook = self.task_warning_hook
        tclass.task_submission_failed_hook = self.task_submission_failed_hook
        tclass.task_timeout_hook = self.task_timeout_hook

        tclass.remote_host = self.host

        # TO DO: can this be moved into task base class?
        tclass.job_submit_method = self.job_submit_method
        tclass.job_submit_log_directory = self.job_submit_log_directory

        tclass.valid_hours = self.hours

        tclass.intercycle = self.intercycle
        tclass.follow_on = self.follow_on_task

        if self.type == 'family':
            tclass.members = self.members

        if self.member_of:
            tclass.member_of = self.member_of

        def tclass_format_prerequisites( sself, preq ):
            m = re.search( '\$\(CYCLE_TIME\s*\-\s*(\d+)\)', preq )
            if m:
                offset = m.groups()[0]
                ctime = cycle_time.decrement( sself.c_time, offset )
                preq = re.sub( '\$\(CYCLE_TIME\s*\-\s*\d+\)', ctime, preq )
            else:
                preq = re.sub( '\$\(CYCLE_TIME\)', sself.c_time, preq )
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

        tclass.add_prerequisites = tclass_add_prerequisites

        # class init function
        def tclass_init( sself, start_c_time, initial_state, stop_c_time=None, startup=False ):
            # adjust cycle time to next valid for this task
            sself.c_time = sself.nearest_c_time( start_c_time )
            sself.stop_c_time = stop_c_time
            sself.tag = sself.c_time
            sself.id = sself.name + '%' + sself.c_time
            sself.c_hour = sself.c_time[8:10]
            sself.orig_c_hour = start_c_time[8:10]
 
            sself.external_tasks = deque()

            for command in self.commands:
                sself.external_tasks.append( command )
 
            if 'clocktriggered' in self.modifiers:
                sself.real_time_delay =  float( self.clocktriggered_offset )

            # prerequisites
            sself.prerequisites = prerequisites()
            sself.add_prerequisites( startup )
            ## should these be conditional too:?
            sself.suicide_prerequisites = plain_prerequisites( sself.id )
            ##sself.add_requisites( sself.suicide_prerequisites, self.suicide_triggers )

            if self.member_of:
                foo = plain_prerequisites( sself.id )
                foo.add( self.member_of + '%' + sself.c_time + ' started' )
                sself.prerequisites.add_requisites( foo )

            # familyfinished prerequisites
            if self.type == 'family':
                sself.familyfinished_prerequisites = plain_prerequisites( sself.id )
                for member in self.members:
                    sself.familyfinished_prerequisites.add( member + '%' + sself.c_time + ' finished' )

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
                        #ctime = cycle_time.decrement( sself.c_time, offset )
                       raise DefinitionError, "ERROR, " + sself.id + ": Output offsets must be positive: " + output
                    else:
                        ctime = cycle_time.increment( sself.c_time, offset )
                    out = re.sub( '\$\(CYCLE_TIME.*\)', ctime, output )
                else:
                    out = re.sub( '\$\(CYCLE_TIME\)', sself.c_time, output )
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

            sself.pre_scripting = self.pre_scripting
            sself.post_scripting = self.post_scripting

            if 'catchup_clocktriggered' in self.modifiers:
                catchup_clocktriggered.__init__( sself )
 
            super( sself.__class__, sself ).__init__( initial_state ) 

        tclass.__init__ = tclass_init

        return tclass
