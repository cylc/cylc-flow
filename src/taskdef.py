#!/usr/bin/env python

# NOT YET IMPLEMENTED OR DOCUMENTED FROM bin/_taskgen:
#   - time translation (for different units) not used
#   - not using the various check_() functions below
#   - conditional prerequisites
#   - short name
#   - asynch stuff, output_patterns
#   - no longer interpolate ctime in env vars or scripting 
#     (not needed since cylcutil?) 
#
#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import sys, re
from OrderedDict import OrderedDict

from prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites import prerequisites
from task_output_logs import logfiles
from collections import deque
from outputs import outputs
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
    allowed_types = [ 'free', 'tied' ]
    allowed_modifiers = [ 'sequential', 'oneoff', 'contact', 'catchup_contact' ]

    def __init__( self, name, short_name=None ):
        self.name = name
        if not short_name:
            self.shortname = name 

        self.type = 'free'
        self.model_coldstart = False  # used in config.py
        self.coldstart = False  # used in config.py
        self.oneoff = False  # used in config.py

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

        self.n_restart_outputs = None
        self.contact_offset = None

        self.prerequisites = OrderedDict()                # list of messages
        self.suicide_prerequisites = OrderedDict()        #  "
        self.coldstart_prerequisites = OrderedDict()      #  "
        self.conditional_prerequisites = OrderedDict()    #  "
        self.outputs = OrderedDict()                      #  "

        self.commands = []                       # list of commands
        self.scripting   = []                    # list of lines
        self.environment = OrderedDict()         # var = value
        self.directives  = OrderedDict()         # var = value

    def load_oldstyle( self, name, tdef, ignore_owner ):
        # tdef direct from configobj [taskdefs][name] section
        self.name = name
        self.description = tdef['description']
        self.job_submission_method = tdef['job submission method']
        self.execution_timeout_minutes = tdef['execution timeout minutes']
        self.reset_execution_timeout_on_incoming_messages = tdef['reset execution timeout on incoming messages']
        self.hours = tdef['cycles']
        self.host = tdef['host']
        if not ignore_owner:
            self.owner = tdef['owner']
        self.follow_on_task = tdef['follow on task']
        self.intercycle = tdef['intercycle']

        self.commands = tdef['command list']

        self.environment = tdef['environment']
        self.directives = tdef['directives']

        #self.scripting = tdef['scripting']

        self.type = tdef['type']

        for item in tdef['type modifier list']:
            if item == 'oneoff' or \
                item == 'sequential' or \
                item == 'catchup':
                self.modifiers.append( item )
                continue
            m = re.match( 'model\(\s*restarts\s*=\s*(\d+)\s*\)', item )
            if m:
                self.type = 'tied'
                self.n_restart_outputs = int( m.groups()[0] )
                continue
            m = re.match( 'clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
            if m:
                self.modifiers.append( 'contact' )
                self.contact_offset = m.groups()[0]
                continue
            m = re.match( 'catchup clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
            if m:
                self.modifiers.append( 'catchup_contact' )
                self.contact_offset = m.groups()[0]
                continue
            raise DefinitionError, 'illegal task type: ' + item

        self.load_requisites( self.prerequisites, tdef['prerequisites'], conditional=True )
        self.load_requisites( self.outputs, tdef['outputs'] )
        self.load_requisites( self.coldstart_prerequisites, tdef['coldstart prerequisites'] )
        self.load_requisites( self.suicide_prerequisites, tdef['suicide prerequisites'] )

        # TO DO: CONDITIONAL PREREQUISITES

    def load_requisites( self, target, source, conditional=False ):
        for item in source:
            if item == 'condition':
                if not conditional:
                    raise DefinitionError( "only prerequisites can be conditional" )
                continue
            if isinstance( source[item], dict ):
                # item is a cycle list
                if item not in target:
                    target[item] = []
                for pre in source[item]:
                    if pre == 'condition':
                        if not conditional:
                            raise DefinitionError( "only prerequisites can be conditional" )
                        continue
                    target[item].append( source[item][pre] )
            else:
                if 'any' not in target:
                    target['any'] = []
                target['any'].append( source[item] )

    def check_name( self, name ):
        m = re.match( '^(\w+),\s*(\w+)$', name )
        if m:
            name, shortname = m.groups()
            if re.search( '[^\w]', shortname ):
                raise DefinitionError( 'Task names may contain only a-z,A-Z,0-9,_' )

        if re.search( '[^\w]', name ):
            raise DefinitionError( 'Task names may contain only a-z,A-Z,0-9,_' )
 
    def check_type( self, type ): 
        if type not in self.__class__.allowed_types:
            raise DefinitionError( 'Illegal task type: ' + type )

    def check_modifier( self, modifier ):
        if modifier not in self.__class__.allowed_modifiers:
            raise DefinitionError( 'Illegal task type modifier: ' + modifier )

    def check_set_hours( self, hours ):
        for hr in hours:
            hour = int( hr )
            if hour < 0 or hour > 23:
                raise DefinitionError( 'Hour must be 0<hour<23' )
            self.hours.append( hour )

    def check_consistency( self ):
        if len( self.hours ) == 0:
            raise DefinitionError( 'no hours specified' )

        if 'contact' in self.modifiers:
            if len( self.contact_offset.keys() ) == 0:
                raise DefinitionError( 'contact tasks must specify a time offset' )

        if self.type == 'tied' and self.n_restart_outputs == 0:
            raise DefinitionError( 'tied tasks must specify number of restart outputs' )

        if 'oneoff' not in self.modifiers and self.intercycle:
            if not self.follow_on_task:
                raise DefinitionError( 'oneoff intercycle tasks must specify a follow-on task' )

        if self.member_of and len( self.members ) > 0:
            raise DefinitionError( 'nested task families are not allowed' )

    #def append_to_condition_list( self, parameter, condition, value ):
    #    if condition in parameter.keys():
    #        parameter[condition].append( value )
    #    else:
    #        parameter[condition] = [ value ]

    #def add_to_condition_dict( self, parameter, condition, var, value ):
    #    if condition in parameter.keys():
    #        parameter[condition][var] = value
    #    else:
    #        parameter[condition] = {}
    #        parameter[condition][var] = value

    #def escape_quotes( self, strng ):
    #    return re.sub( '([\\\'"])', r'\\\1', strng )

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

        tclass = type( self.name, tuple( base_types), dict())
        tclass.name = self.name        # TO DO: NOT NEEDED, USED class.__name__
        tclass.short_name = self.name  # TO DO: reimplement short name
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

        def tclass_interpolate_ctime( sself, str ):
            # replace $(CYCLE_TIME +/- N)
            req = str
            m = re.search( '\$\(\s*CYCLE_TIME\s*\+\s*(\d+)\s*\)', req )
            if m:
                req = re.sub( '\$\(\s*CYCLE_TIME.*\)', cycle_time.increment( sself.c_time ), req )
            m = re.search( '\$\(\s*CYCLE_TIME\s*\-\s*(\d+)\s*\)', req )
            if m:
                req = re.sub( '\$\(\s*CYCLE_TIME.*\)', cycle_time.decrement( sself.c_time ), req )
            req = re.sub( '\$\(\s*CYCLE_TIME\s*\)', sself.c_time, req )
            return req

        tclass.interpolate_ctime = tclass_interpolate_ctime

        def tclass_add_requisites( sself, target, source ):
            # target: requisites object
            # source conditional taskdef requisites
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
 
            sself.external_tasks = deque()

            for command in self.commands:
                sself.external_tasks.append( command )
 
            if 'contact' in self.modifiers:
                sself.real_time_delay =  int( self.contact_offset )

            # prerequisites
            sself.prerequisites = prerequisites( sself.id )
            sself.add_requisites( sself.prerequisites, self.prerequisites )
            # suicide prerequisites
            sself.suicide_prerequisites = prerequisites( sself.id )
            sself.add_requisites( sself.suicide_prerequisites, self.suicide_prerequisites )

            if self.member_of:
                # TO DO: AUTOMATE THIS PREREQ ADDITION FOR A FAMILY MEMBER?
                sself.prerequisites.add( self.member_of + '%' + sself.c_time + ' started' )

            # familyfinished prerequisites
            if self.type == 'family':
                # TO DO: AUTOMATE THIS PREREQ ADDITION FOR A FAMILY MEMBER?
                sself.familyfinished_prerequisites = prerequisites( sself.id )
                for member in self.members:
                    sself.familyfinished_prerequisites.add( member + '%' + sself.c_time + ' finished' )

            sself.logfiles = logfiles()
            for lfile in self.logfiles:
                sself.logfiles.add_path( lfile )

            # outputs
            sself.outputs = outputs( sself.id )
            sself.add_requisites( sself.outputs, self.outputs )

            if self.type == 'tied':
                sself.register_restart_requisites( self.n_restart_outputs )

            sself.outputs.register()

            if startup and len( self.coldstart_prerequisites.keys()) != 0:
                # ADD coldstart prerequisites AT STARTUP
                # (Uncomment next line to OVERRIDE existing prerequisites:)
                #    sself.prerequisites = prerequisites( sself.id )
                sself.add_requisites( sself.prerequisites, self.coldstart_prerequisites )

            sself.env_vars = OrderedDict()
            sself.env_vars['TASK_NAME'] = sself.name
            sself.env_vars['TASK_ID'] = sself.id
            sself.env_vars['CYCLE_TIME'] = sself.c_time
       
            for var in self.environment:
                val = self.environment[ var ]
                # TO DO: QUOTING OF VAL?
                sself.env_vars[ var ] = val

            sself.directives = OrderedDict()
            for var in self.directives:
                val = self.directives[ var ]
                # TO DO: QUOTING OF VAL?
                sself.directives[ var ] = val

            sself.extra_scripting = self.scripting

            if 'catchup_contact' in self.modifiers:
                catchup_contact.__init__( sself )
 
            super( sself.__class__, sself ).__init__( initial_state ) 

        tclass.__init__ = tclass_init

        return tclass
