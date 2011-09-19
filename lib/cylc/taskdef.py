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

# THIS MODULE HANDLES DYNAMIC DEFINITION OF TASK PROXY CLASSES according
# to information parsed from the suite.rc file via config.py. It could 
# probably do with some refactoring to make it more transparent ...

# TO DO : ONEOFF FOLLOWON TASKS: still needed but can now be identified
# automatically from the dependency graph?

import sys, re
from OrderedDict import OrderedDict

from prerequisites.prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites.prerequisites_loose import loose_prerequisites
from prerequisites.prerequisites import prerequisites
from prerequisites.plain_prerequisites import plain_prerequisites
from prerequisites.conditionals import conditional_prerequisites
from task_output_logs import logfiles
from collections import deque
from outputs import outputs
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
        if re.search( '[^0-9a-zA-Z_\.]', name ):
            # dot for namespace syntax.
            # regex [\w] allows spaces.
            raise DefinitionError, "ERROR: Illegal task name: " + name

        self.name = name
        self.type = 'free'
        self.job_submit_method = None
        self.job_submission_shell = None
        self.job_submit_command_template = None
        self.job_submit_log_directory = None
        self.manual_messaging = False
        self.modifiers = []
        self.asyncid_pattern = None

        self.remote_host = None
        self.owner = None
        self.remote_shell_template = None
        self.remote_cylc_directory = None
        self.remote_suite_directory = None
        self.remote_log_directory = None

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

        self.follow_on_task = None

        self.clocktriggered_offset = None

        # triggers[0,6] = [ A, B:1, C(T-6), ... ]
        self.triggers = OrderedDict()         
        # cond[6,18] = [ '(A & B)|C', 'C | D | E', ... ]
        self.cond_triggers = OrderedDict()             
        self.startup_triggers = OrderedDict()
        self.suicide_startup_triggers = OrderedDict()
        self.suicide_triggers = OrderedDict()       
        self.suicide_cond_triggers = OrderedDict()
        self.asynchronous_triggers = []
        self.startup_cond_triggers = OrderedDict()
        self.suicide_startup_cond_triggers = OrderedDict()

        self.outputs = []     # list of special outputs; change to OrderedDict()
                              # if need to vary per cycle.

        self.loose_prerequisites = [] # asynchronous tasks

        self.commands = [] # list of commands
        self.precommand = None
        self.postcommand = None

        self.environment = OrderedDict()  # var = value
        self.directives  = OrderedDict()  # var = value

    def add_trigger( self, msg, validity, suicide=False ):
        if suicide:
            if validity not in self.suicide_triggers:
                self.suicide_triggers[ validity ] = []
            self.suicide_triggers[ validity ].append( msg )
        else:
            if validity not in self.triggers:
                self.triggers[ validity ] = []
            self.triggers[ validity ].append( msg )

    def add_asynchronous_trigger( self, msg ):
        self.asynchronous_triggers.append( msg )

    def add_startup_trigger( self, msg, validity, suicide=False ):
        if suicide:
            if validity not in self.suicide_startup_triggers:
                self.suicide_startup_triggers[ validity ] = []
            self.suicide_startup_triggers[ validity ].append( msg )
        else:
            if validity not in self.startup_triggers:
                self.startup_triggers[ validity ] = []
            self.startup_triggers[ validity ].append( msg )

    def add_conditional_trigger( self, triggers, exp, validity, suicide=False ):
        # triggers[label] = trigger
        # expression relates the labels
        if suicide:
            if validity not in self.suicide_cond_triggers:
                self.suicide_cond_triggers[ validity ] = []
            self.suicide_cond_triggers[ validity ].append( [ triggers, exp ] )
        else:
            if validity not in self.cond_triggers:
                self.cond_triggers[ validity ] = []
            self.cond_triggers[ validity ].append( [ triggers, exp ] )

    def add_startup_conditional_trigger( self, triggers, exp, validity, suicide=False ):
        # triggers[label] = trigger
        # expression relates the labels
        if suicide:
            if validity not in self.suicide_startup_cond_triggers:
                self.suicide_startup_cond_triggers[ validity ] = []
            self.suicide_startup_cond_triggers[ validity ].append( [ triggers, exp ] )
        else:
            if validity not in self.startup_cond_triggers:
                self.startup_cond_triggers[ validity ] = []
            self.startup_cond_triggers[ validity ].append( [ triggers, exp ] )

    def set_valid_hours( self, section ):
        if re.match( '^[\s,\d]+$', section ):
            # Cycling task.
            hours = re.split( '\s*,\s*', section )
            for hr in hours:
                hour = int( hr )
                if hour < 0 or hour > 23:
                    raise DefinitionError( 'ERROR: Hour ' + str(hour) + ' must be between 0 and 23' )
                if hour not in self.hours: 
                    self.hours.append( hour )
            self.hours.sort( key=int )
        else:
            raise DefinitionError( 'ERROR: Illegal graph valid hours: ' + section )

    def check_consistency( self ):
        # TO DO: this is not currently used.
        if len( self.hours ) == 0:
            raise DefinitionError( 'ERROR: no hours specified' )

        if 'clocktriggered' in self.modifiers:
            if self.clocktriggered_offset == None:
                raise DefinitionError( 'ERROR: clock-triggered tasks must specify a time offset' )

    def time_trans( self, strng, hours=False ):
        # Time unit translation.
        # THIS IS NOT CURRENTLY USED, but may be useful in the future.
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
            # __import__() keyword args were introduced in Python 2.5
            #mod = __import__( 'cylc.task_types.' + foo, fromlist=[foo] )
            mod = __import__( 'cylc.task_types.' + foo, globals(), locals(), [foo] )
            base_types.append( getattr( mod, foo ) )

        tclass = type( self.name, tuple( base_types), dict())
        tclass.name = self.name        # TO DO: NOT NEEDED, USED class.__name__
        tclass.instance_count = 0
        tclass.upward_instance_count = 0
        tclass.description = self.description

        tclass.elapsed_times = []
        tclass.mean_total_elapsed_time = None

        tclass.timeouts = self.timeouts
        tclass.hook_scripts = self.hook_scripts

        tclass.remote_host = self.remote_host
        tclass.owner = self.owner
        tclass.remote_shell_template = self.remote_shell_template
        tclass.remote_cylc_directory = self.remote_cylc_directory
        tclass.remote_suite_directory = self.remote_suite_directory
        tclass.remote_log_directory = self.remote_log_directory

        tclass.job_submit_method = self.job_submit_method
        tclass.job_submission_shell = self.job_submission_shell
        tclass.job_submit_command_template = self.job_submit_command_template
        tclass.job_submit_log_directory = self.job_submit_log_directory
        tclass.manual_messaging = self.manual_messaging

        tclass.valid_hours = self.hours

        tclass.intercycle = self.intercycle
        tclass.follow_on = self.follow_on_task

        def tclass_format_prerequisites( sself, preq ):
            m = re.search( '\$\(TAG\s*\-\s*(\d+)\)', preq )
            if m:
                offset = m.groups()[0]
                if self.type != 'async_repeating' and self.type != 'async_daemon' and self.type != 'async_oneoff':
                    # cycle time decrement
                    foo = ct( sself.c_time )
                    foo.decrement( hours=offset )
                    ctime = foo.get()
                    preq = re.sub( '\$\(TAG\s*\-\s*\d+\)', ctime, preq )
                else:
                    # arithmetic decrement
                    foo = sself.tag - offset
                    preq = re.sub( '\$\(TAG\s*\-\s*\d+\)', foo, preq )

            elif re.search( '\$\(TAG\)', preq ):
                preq = re.sub( '\$\(TAG\)', sself.tag, preq )

            return preq
        tclass.format_prerequisites = tclass_format_prerequisites 

        def tclass_add_prerequisites( sself, startup ):
            # plain triggers
            pp = plain_prerequisites( sself.id ) 
            if startup:
                triggers = dict( self.triggers.items() + self.startup_triggers.items() )
            else:
                triggers = self.triggers
            for val in triggers:
                for trig in triggers[ val ]:
                    if val != "once" and not re.match( '^ASYNCID:', val ):
                        hours = re.split( ',\s*', val )
                        ihours = [ int(i) for i in hours ]
                        if int( sself.c_hour ) not in ihours:
                            continue
                    pp.add( sself.format_prerequisites( trig ))
            sself.prerequisites.add_requisites( pp )

            # plain suicide triggers
            if startup:
                triggers = dict( self.suicide_triggers.items() + self.suicide_startup_triggers.items() )
            else:
                triggers = self.suicide_triggers
            pp = plain_prerequisites( sself.id ) 
            for val in triggers:
                for trig in triggers[ val ]:
                    if val != "once" and not re.match( '^ASYNCID:', val ):
                        hours = re.split( ',\s*', val )
                        ihours = [ int(i) for i in hours ]
                        if int( sself.c_hour ) not in ihours:
                            continue
                    pp.add( sself.format_prerequisites( trig ))
            sself.suicide_prerequisites.add_requisites( pp )

            # conditional triggers
            if startup:
                ctriggers = dict( self.cond_triggers.items() + self.startup_cond_triggers.items() )
            else:
                ctriggers = self.cond_triggers

            for val in ctriggers.keys():
                for ctrig in ctriggers[ val ]:
                    triggers, exp =  ctrig
                    if val != "once" and not re.match( '^ASYNCID:', val ):
                        hours = re.split( ',\s*', val )
                        ihours = [ int(i) for i in hours ]
                        if int( sself.c_hour ) not in ihours:
                            continue
                    cp = conditional_prerequisites( sself.id )
                    for label in triggers:
                        trig = triggers[label]
                        cp.add( sself.format_prerequisites( trig ), label )
                    cp.set_condition( exp )
                    sself.prerequisites.add_requisites( cp )

            # conditional suicide triggers
            if startup:
                ctriggers = dict( self.suicide_cond_triggers.items() + self.suicide_startup_cond_triggers.items() )
            else:
                ctriggers = self.suicide_cond_triggers
            for val in ctriggers:
                for ctrig in ctriggers[ val ]:
                    triggers, exp =  ctrig
                    if val != "once" and not re.match( '^ASYNCID:', val ):
                        hours = re.split( ',\s*', val )
                        ihours = [ int(i) for i in hours ]
                        if int( sself.c_hour ) not in ihours:
                            continue
                    cp = conditional_prerequisites( sself.id )
                    for label in triggers:
                        trig = triggers[label]
                        cp.add( sself.format_prerequisites( trig ), label )
                    cp.set_condition( exp )
                    sself.suicide_prerequisites.add_requisites( cp )

            if len( self.loose_prerequisites ) > 0:
                lp = loose_prerequisites(sself.id)
                for pre in self.loose_prerequisites:
                    lp.add( pre )
                sself.prerequisites.add_requisites( lp )

            if len( self.asynchronous_triggers ) > 0:
                pp = plain_prerequisites( sself.id ) 
                for trigger in self.asynchronous_triggers:
                    pp.add( sself.format_prerequisites( trigger ))
                sself.prerequisites.add_requisites( pp )

        tclass.add_prerequisites = tclass_add_prerequisites

        # class init function
        def tclass_init( sself, start_c_time, initial_state, stop_c_time=None, startup=False ):
            sself.tag = sself.adjust_tag( start_c_time )
            if self.type != 'async_repeating' and self.type != 'async_daemon' and self.type != 'async_oneoff':
                sself.c_time = sself.tag
                sself.c_hour = sself.c_time[8:10]
                sself.orig_c_hour = start_c_time[8:10]
 
            sself.id = sself.name + '%' + sself.tag
            sself.external_tasks = deque()
            sself.asyncid_pattern = self.asyncid_pattern

            for command in self.commands:
                sself.external_tasks.append( command )
            sself.precommand = self.precommand
            sself.postcommand = self.postcommand
 
            if 'clocktriggered' in self.modifiers:
                sself.real_time_delay =  float( self.clocktriggered_offset )

            # prerequisites
            sself.prerequisites = prerequisites()
            sself.suicide_prerequisites = prerequisites()
            sself.add_prerequisites( startup )

            sself.logfiles = logfiles()
            for lfile in self.logfiles:
                sself.logfiles.add_path( lfile )

            # outputs
            sself.outputs = outputs( sself.id )
            for output in self.outputs:
                m = re.search( '\$\(TAG\s*([+-])\s*(\d+)\)', output )
                if m:
                    sign, offset = m.groups()
                    if sign == '-':
                       raise DefinitionError, "ERROR, " + sself.id + ": Output offsets must be positive: " + output
                    else:
                        # TO DO: GENERALIZE FOR ASYNC TASKS
                        foo = ct( sself.c_time )
                        foo.increment( hours=offset )
                        ctime = foo.get()
                    out = re.sub( '\$\(TAG.*\)', ctime, output )
                elif re.search( '\$\(TAG\)', output ):
                    out = re.sub( '\$\(TAG\)', sself.tag, output )
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
