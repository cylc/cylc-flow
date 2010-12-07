#!/usr/bin/env python

# TO DO: CONDITIONALS ON CYCLE HOUR

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import re, string
from OrderedDict import OrderedDict

class Error( Exception ):
    """base class for exceptions in this module."""
    pass

class DefinitionError( Error ):
    """
    Exception raise for errors in taskdef initialization.
    Attributes:
        element - taskdef element causing the problem
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg

class taskdef:
    allowed_types = [ 'free', 'tied' ]
    allowed_modifiers = [ 'sequential', 'oneoff', 'dummy', 'contact', 'catchup_contact' ]

    allowed_keys = [ 'LOGFILES', 'INHERIT', 'TASK', 'OWNER', 'HOURS',
            'COMMAND', 'REMOTE_HOST', 'DIRECTIVES', 'SCRIPTING',
            'ENVIRONMENT', 'INTERCYCLE', 'PREREQUISITES',
            'COLDSTART_PREREQUISITES', 'SUICIDE_PREREQUISITES',
            'OUTPUTS', 'N_RESTART_OUTPUTS', 'TYPE', 'CONTACT_DELAY',
            'DESCRIPTION', 'OUTPUT_PATTERNS', 'FOLLOW_ON', 'FAMILY',
            'MEMBERS', 'MEMBER_OF' ]

    def __init__( self, name, shortname=None ):
        self.check_name( name )
        self.name = name
        # IGNORING SHORT NAME FOR NOW
        #self.shortname = shortname

        self.intercycle = False
        self.n_restart_outputs = 0

        self.hours = []
        self.logfiles = []
        self.description = []
        self.prerequisites = []
        self.suicide_prerequisites = []
        self.coldstart_prerequisites = []
        self.conditional_prerequisites = {}
        self.modifiers = []
        self.outputs = []
        self.commandlist = []
        self.scripting = []
        self.environment = OrderedDict()
        self.directives = OrderedDict()
        self.members = []

        self.member_of = None
        self.owner = None
        self.host = None

    def dump( self ):
        indent = '   '
        print 'NAME'
        print  indent, self.name

        print 'DESCRIPTION'
        for line in self.description:
            print indent, line

        print 'TYPE'
        types = [ self.type ] + self.modifiers
        print indent, ', '.join( types )

        print 'COMMAND'
        for command in self.commandlist:
            print indent, command

        if self.owner:
            print 'OWNER'
            print indent, self.owner

        if self.host:
            print 'HOST'
            print indent, self.host

        print 'PREREQUISITES'
        if len( self.prerequisites ) == 0:
            print "(none)"
        else:
            for prerequisite in self.prerequisites:
                print indent, prerequisite

        print 'OUTPUTS'
        if len( self.outputs ) == 0:
            print "(none)"
        else:
            for output in self.outputs:
                print indent, output

        print 'ENVIRONMENT'
        for var in self.environment:
            print indent, var, self.environment[ var ]


    def check_name( self, name ):
        if re.search( '[^\w]', name ):
            raise DefinitionError( 'Task names may contain only a-z,A-Z,0-9,_' )
 
    def add_description( self, line ):
        self.description.append( line )

    def set_type( self, type ): 
        if type not in self.__class__.allowed_types:
            raise DefinitionError( 'Illegal task type: ' + type )
        self.type = type

    def add_modifier( self, modifier ):
        if modifier not in self.__class__.allowed_modifiers:
            raise DefinitionError( 'Illegal task type modifier: ' + modifier )
        self.modifiers.append( modifier )

    def set_hours( self, hours=[] ):
        for hr in hours:
            hour = int( hr )
            if hour < 0 or hour > 23:
                raise DefinitionError( 'Hour must be 0<hour<23' )
            self.hours.append( hour )

    def add_command( self, command ):
        self.commandlist.append( command )

    def add_prerequisite( self, msg ):
        self.prerequisites.append( msg )

    def add_suicide_prerequisite( self, msg ):
        self.suicide_prerequisites.append( msg )

    def add_coldstart_prerequisite( self, msg ):
        self.coldstart_prerequisites.append( msg )

    def add_conditional_prerequisite( self, label, msg ):
        self.conditional_prerequisites[ label ] = msg

    def set_conditional_expression( self, expr ):
        # TO DO: MAKE THIS WORK
        # check consistent with prerequisites added
        self.conditional_expression = expr

    def add_output( self, msg ):
        self.outputs.append( msg )

    def set_member_of( self, family ):
        self.member_of = family

    def add_member( self, member ):
        self.members.append( member )

    def set_host( self, host ):
        self.host = host

    def set_owner( self, owner ):
        self.owner = owner

    def set_contact_offset( self, offset ):
        self.contact_offset = int( offset )

    def add_environment( self, var, value ):
        self.environment[ var ] = value

    def add_directive( self, var, value ):
        self.environment[ var ] = value

    def add_scripting( self, line ):
        self.scripting.append( line )

    def set_n_restart_outputs( self, n ):
        self.n_restart_outputs = int(n)

    def set_has_intercycle_dependants( self ):
        self.intercycle = True

    def set_follow_on_task( self, task ):
        self.follow_on_task = task

    def set_inherit( self, taskdef ):
        # TO DO: DEEPCOPY AND OVERRIDE CERTAIN ELEMENTS?
        pass

    def add_logfile( self, log ):
        self.logfiles.append( log )

    def check_consistency( self ):
        if len( self.hours ) == 0:
            raise DefinitionError( 'no hours specified' )

        if 'contact' in self.modifiers:
            if not self.contact_offset:
                raise DefinitionError( 'contact tasks must specify a time offset' )

        if self.type == 'tied' and self.n_restart_outputs == 0:
            raise DefinitionError( 'tied tasks must specify number of restart outputs' )

        if 'oneoff' not in self.modifiers and self.intercycle:
            if not self.follow_on:
                raise DefinitionError( 'oneoff intercycle tasks must specify a follow-on task' )

        if self.member_of and len( self.members ) > 0:
            raise DefinitionError( 'nested task families are not allowed' )

    def load_from_taskdef_file( self, file ):
        print 'Loading', file
        DEF = open( file, 'r' )
        lines = DEF.readlines()
        DEF.close()

        delay = 0
        catchup_contact = False
        sequential = False
        contact = False
        oneoff = False
        dummy = False
        task_type = None

        # PARSE THE TASKDEF FILE----------------------------
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

            # warn of possible illegal trailing comments
            if re.search( '#', line ):
                print 'WARNING: possible illegal trailing comment detected:'
                print '   --> ', line
                print "(OK if the '#' is part of a string or shell variable expansion)"

            #### detect conditionals:
            ###m = re.match( '^\s*if HOUR in \s*([\d,]+)\s*:', lline )
            ###if m:
            ###    #print '!   ', condition
            ###    condition = m.groups()[0]
            ###    parsed_def[ current_key ][ condition ] = []
            ###    continue
        
            if re.match( '^%.*', line ):
                # new key identified
                ###condition = 'any'
                key = string.lstrip( line, '%' )
                # always define an 'any' key
                if key not in self.__class__.allowed_keys:
                    raise DefintionError( 'ILLEGAL KEY: ' + key )

            else:
                # process data associated with current key
                value = line

                if key == 'FAMILY':
                    self.set_member_of( value )
 
                elif key == 'MEMBERS':
                    self.add_member( value )

                elif key == 'INTERCYCLE':
                    if value == 'True' or value == 'true':
                        self.set_intercycle()

                elif key == 'TYPE':
                    typelist = re.split( r', *', value )
                    self.set_type( typelist[0] )
                    if len( typelist ) > 1:
                        for modifier in typelist[1:]:
                            self.add_modifier( modifier )

                elif key == 'COMMAND':
                    self.add_command( value )

                elif key == 'ENVIRONMENT':
                    evar, evalue = value.split( ' ', 1 )
                    self.add_scripting( evar, evalue )

                elif key == 'SCRIPTING':
                    self.add_scripting( value )

                elif key == 'LOGFILES':
                    self.add_logfile( value )

                elif key == 'DIRECTIVES':
                    self.add_directive( value )

                elif key == 'FOLLOW_ON':
                    self.set_follow_on_task( value )

                elif key == 'CONTACT_DELAY':
                    self.set_contact_offset( value )

                elif key == 'N_RESTART_OUTPUTS':
                    self.set_n_restart_outputs( value )

                elif key == 'DESCRIPTION':
                    self.add_description( value )

                elif key == 'OWNER':
                    self.set_owner( value )

                elif key == 'REMOTE_HOST':
                    self.set_host( value )

                elif key == 'HOURS':
                    hours = re.split( r', *', value )
                    self.set_hours( hours )
 
                elif key == 'PREREQUISITES':
                    self.add_prerequisite( value )

                elif key == 'OUTPUTS':
                    self.add_output( value )

                elif key == 'COLDSTART_PREREQUISITES':
                    self.add_coldstart_prerequisite( value )

                elif key == 'SUICIDE_PREREQUISITES':
                    self.add_suicide_prerequisite( value )

                elif key == 'CONDITIONAL_PREREQUISITES':
                    label, message = value.split( ' ', 1 )
                    self.add_conditional_prerequisite( label, message )
        
        self.check_consistency()
