#!/usr/bin/env python

# NOT YET IMPLEMENTED OR DOCUMENTED FROM bin/_taskgen:
#   - time translation (for different units) not used
#   - not using the various check_() functions below
#   - asynch stuff, output_patterns

# ONEOFF and FOLLOWON TASKS: followon still needed but can now be
# identified automatically from the dependency graph?
 
import sys, re
from OrderedDict import OrderedDict

from prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites import prerequisites
from plain_prerequisites import plain_prerequisites
from conditionals import conditional_prerequisites
from task_output_logs import logfiles
from collections import deque
from outputs import outputs
import cycle_time
from graphnode import graphnode

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
        self.name = name
        self.type = 'free'
        self.job_submit_method = 'background'
        self.modifiers = []

        self.owner = None
        self.host = None
        self.execution_timeout_minutes = None
        self.reset_execution_timeout_on_incoming_message = False

        self.intercycle = False
        self.hours = []
        self.logfiles = []
        self.description = ['Task description has not been completed' ]

        self.members = []
        self.member_of = None
        self.follow_on_task = None

        self.contact_offset = None

        # triggers[0,6] = [ A, B:1, C(T-6), ... ]
        self.triggers = OrderedDict()         
        # cond[6,18] = [ '(A & B)|C', 'C | D | E', ... ]
        self.cond_triggers = OrderedDict()             
        self.startup_triggers = OrderedDict()
        self.suicide_triggers = OrderedDict()       

        self.outputs = OrderedDict()             # out[label] = message

        self.commands = []                       # list of commands
        self.scripting   = []                    # list of lines
        self.environment = OrderedDict()         # var = value
        self.directives  = OrderedDict()         # var = value

    def add_trigger( self, trigger, cycle_list_string ):
        if cycle_list_string not in self.triggers:
            self.triggers[ cycle_list_string ] = []
        self.triggers[ cycle_list_string ].append( trigger )

    def add_startup_trigger( self, trigger, cycle_list_string ):
        if cycle_list_string not in self.startup_triggers:
            self.startup_triggers[ cycle_list_string ] = []
        self.startup_triggers[ cycle_list_string ].append( trigger )

    def add_conditional_trigger( self, trigger, cycle_list_string ):
        if cycle_list_string not in self.cond_triggers:
            self.cond_triggers[ cycle_list_string ] = []
        self.cond_triggers[ cycle_list_string ].append( trigger )

    def check_name( self, name ):
        if re.search( '[^\w]', name ):
            raise DefinitionError( 'Task names may contain only a-z,A-Z,0-9,_' )
 
    def add_hours( self, hours ):
        for hr in hours:
            hour = int( hr )
            if hour < 0 or hour > 23:
                raise DefinitionError( 'Hour must be 0<hour<23' )
            if hour not in self.hours: 
                self.hours.append( hour )
            self.hours.sort( key=int )

    def check_consistency( self ):
        if len( self.hours ) == 0:
            raise DefinitionError( 'no hours specified' )

        if 'contact' in self.modifiers:
            if self.contact_offset == None:
                raise DefinitionError( 'contact tasks must specify a time offset' )

        if self.member_of and len( self.members ) > 0:
            raise DefinitionError( 'nested task families are not allowed' )

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

        if self.owner:
            tclass.owner = self.owner
        else:
            # TO DO: can we just just default None at init here?
            tclass.owner = None

        if self.execution_timeout_minutes:
            tclass.execution_timeout_minutes = self.execution_timeout_minutes
        else:
            tclass.execution_timeout_minutes = None

        tclass.reset_execution_timeout_on_incoming_messages = self.reset_execution_timeout_on_incoming_messages

        if self.host:
            tclass.remote_host = self.host
        else:
            # TO DO: can we just just default None at init here?
            tclass.remote_host = None

        # TO DO: can this be moved into task base class?
        tclass.job_submit_method = self.job_submit_method

        tclass.valid_hours = self.hours

        tclass.intercycle = self.intercycle
        if self.follow_on_task:
            # TO DO: can we just just default None at init here?
            tclass.follow_on = self.follow_on_task

        if self.type == 'family':
            tclass.members = self.members

        if self.member_of:
            tclass.member_of = self.member_of

        def tclass_format_trigger( sself, trigger ):
            node = graphnode( trigger )
            name = node.name
            if node.intercycle:
                offset = node.intercycle_offset
                msg = name + '%' + cycle_time.decrement( sself.c_time, offset ) + ' finished'
                if node.special_output:
                    # trigger of the special output, intercycle
                    raise TaskDefinitionError, "TO DO: INTERCYCLE SPECIAL OUTPUTS"
            else:
                if node.special_output:
                    #raise TaskDefinitionError, "TO DO: SPECIAL OUTPUTS"
                    # trigger of the special output
                    msg = self.outputs[ node.special_output ]
                    re.sub( '$(CYCLE_TIME', sself.c_time, msg )
                else:
                    # trigger off task finished
                    msg = name + '%' + sself.c_time + ' finished'

            return [name, msg]

        tclass.format_trigger = tclass_format_trigger

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
                                pp.add( sself.format_trigger( trig )[1] )
                if found:
                    sself.prerequisites.add_requisites( pp )

            # plain triggers
            for cycles in self.triggers:
                trigs = self.triggers[ cycles ]
                hours = re.split( ',\s*', cycles )
                for hr in hours:
                    if int( sself.c_hour ) == int( hr ):
                        for trig in trigs:
                            pp.add( sself.format_trigger( trig )[1] )
            sself.prerequisites.add_requisites( pp )

            # conditional triggers
            for cycles in self.cond_triggers:
                ctrigs = self.cond_triggers[ cycles ]
                hours = re.split( ',\s*', cycles )
                for hr in hours:
                    if int( sself.c_hour ) == int( hr ):
                        for ctrig in ctrigs:
                            # individual task names
                            cp = conditional_prerequisites( sself.id )
                            names = re.split( '\s*[\|&]\s*', ctrig )
                            for name in names:
                                n, t = sself.format_trigger( name )
                                cp.add( t, n )
                            # strip (T-DD), :foo, off expression
                            exp = re.sub( '\(.*?\)', '', ctrig )  # does more than one (T-DD)?
                            exp = re.sub( ':\w+', '', exp )
                            cp.set_condition( exp )
                            sself.prerequisites.add_requisites( cp )

        tclass.add_prerequisites = tclass_add_prerequisites

        # SPECIAL OUTPUTS AND INTERCYLE DEPS -taken from old config.py
        #if left.output:
        #    # trigger off specific output of previous task
        #    if cycle_list_string not in self.taskdefs[left.name].outputs:
        #        self.taskdefs[left.name].outputs[cycle_list_string] = []
        #    msg = self['tasks'][left.name]['outputs'][left.output]
        #    if msg not in self.taskdefs[left.name].outputs[ cycle_list_string ]:
        #        self.taskdefs[left.name].outputs[ cycle_list_string ].append( msg )
        #    if left.intercycle:
        #        self.taskdefs[left.name].intercycle = True
        #        msg = self.prerequisite_decrement( msg, left.offset )
        #    self.taskdefs[right.name].prerequisites[ cycle_list_string ].append( msg )
        #else:
        #    # trigger off previous task finished
        #    msg = left.name + "%$(CYCLE_TIME) finished" 
        #    if left.intercycle:
        #        self.taskdefs[left.name].intercycle = True
        #        msg = self.prerequisite_decrement( msg, left.offset )
        #    self.taskdefs[right.name].prerequisites[ cycle_list_string ].append( msg )


        def tclass_add_requisites( sself, target, source ):
            # target: requisites object
            # source taskdef requisites
            for condition in source:
                reqs = source[ condition ]
                if condition == 'any':
                    for req in reqs:
                        req = sself.interpolate_ctime( req )
                        target.add( req )
                else:
                    hours = re.split( ',\s*', condition )
                    for hr in hours:
                        if int( sself.c_hour ) == int( hr ):
                            for req in reqs:
                                req = sself.interpolate_ctime( req )
                                target.add( req )

        tclass.add_requisites = tclass_add_requisites

        # class init function
        def tclass_init( sself, c_time, initial_state, startup = False ):
            # adjust cycle time to next valid for this task
            sself.c_time = sself.nearest_c_time( c_time )
            sself.tag = sself.c_time
            sself.id = sself.name + '%' + sself.c_time
            #### FIXME FOR ASYNCHRONOUS TASKS
            sself.c_hour = sself.c_time[8:10]
            sself.orig_c_hour = c_time[8:10]
 
            sself.external_tasks = deque()

            for command in self.commands:
                sself.external_tasks.append( command )
 
            if 'contact' in self.modifiers:
                sself.real_time_delay =  float( self.contact_offset )

            # prerequisites

            sself.prerequisites = prerequisites()
            sself.add_prerequisites( startup )
            # should these be conditional too:?
            sself.suicide_prerequisites = plain_prerequisites( sself.id )
            #sself.add_requisites( sself.suicide_prerequisites, self.suicide_triggers )

            #if self.member_of:
            #    # TO DO: AUTOMATE THIS PREREQ ADDITION FOR A FAMILY MEMBER?
            #    sself.prerequisites.add( self.member_of + '%' + sself.c_time + ' started' )

            ## familyfinished prerequisites
            #if self.type == 'family':
            #    # TO DO: AUTOMATE THIS PREREQ ADDITION FOR A FAMILY MEMBER?
            #    sself.familyfinished_prerequisites = prerequisites( sself.id )
            #    for member in self.members:
            #        sself.familyfinished_prerequisites.add( member + '%' + sself.c_time + ' finished' )

            sself.logfiles = logfiles()
            for lfile in self.logfiles:
                sself.logfiles.add_path( lfile )

            # outputs
            sself.outputs = outputs( sself.id )
            #sself.add_requisites( sself.outputs, self.outputs )

            sself.outputs.register()

            sself.env_vars = OrderedDict()
            for var in self.environment:
                val = self.environment[ var ]
                sself.env_vars[ var ] = val

            sself.directives = OrderedDict()
            for var in self.directives:
                val = self.directives[ var ]
                sself.directives[ var ] = val

            sself.extra_scripting = self.scripting

            if 'catchup_contact' in self.modifiers:
                catchup_contact.__init__( sself )
 
            super( sself.__class__, sself ).__init__( initial_state ) 

        tclass.__init__ = tclass_init

        return tclass
