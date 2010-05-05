#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

#import pdb
import sys, re
from task import task
from mod_nopid import nopid

class asynchronous( nopid, task ):
    # a non-cycling task with no previous instance dependence (so it
    # spawns when it first enters the running state).

    used_outputs = {}
    
    def __init__( self, state, no_reset ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * prerequisites and outputs
        #  * self.env_vars 

        # Top level derived classes must define:
        #   self.id 
        #   <class>.instance_count = 0

        m = re.match( '(.*) \| (.*)', state )
        if m:
            # loading from state dump
            ( self.asyncid, state ) = m.groups()
            self.set_requisites()
            self.env_vars[ 'ASYNCID' ] = self.asyncid 
            if re.search( 'running', state ):
                self.prerequisites.set_all_satisfied()
        else:
            self.asyncid = 'UNSET'

        task.__init__( self, state, no_reset )


    def next_tag( self ):
        return str( int( self.tag ) + 1 )

    def check_requisites( self ):
        for message in self.prerequisites.get_satisfied_list():
            # record which outputs already been used by this task type
            self.__class__.used_outputs[ message ] = True

            if message in self.prerequisites.match_group.keys():
                # IS THIS TOP LEVEL 'IF' NECESSARY?
                mg = self.prerequisites.match_group[ message ]

                for output in self.outputs.get_list():
                    m = re.match( '^(.*)\((.*)\)(.*)', output )
                    if m:
                        (left, mid, right) = m.groups()
                        newout = left + mg + right

                        del self.outputs.satisfied[ output ]
                        self.outputs.satisfied[ newout ] = False

                        self.env_vars[ 'ASYNCID' ] = mg 
                        self.asyncid = mg

                for deathpre in self.death_prerequisites.get_list():
                    m = re.match( '^(.*)\((.*)\)(.*)', deathpre )
                    if m:
                        (left, mid, right) = m.groups()
                        newpre = left + mg + right

                        del self.death_prerequisites.satisfied[ deathpre ]
                        self.death_prerequisites.satisfied[ newpre ] = False

    def set_requisites( self ):
        #pdb.set_trace()
        mg = self.asyncid
        for pre in self.prerequisites.get_list():
            m = re.match( '^(.*)\((.*)\)(.*)', pre )
            if m:
                (left, mid, right) = m.groups()
                if re.match( mid, self.asyncid ):
                    newpre = left + mg + right

                    del self.prerequisites.satisfied[ pre ]
                    self.prerequisites.satisfied[ newpre ] = False
                    self.__class__.used_outputs[ newpre ] = True

        for output in self.outputs.get_list():
            m = re.match( '^(.*)\((.*)\)(.*)', output )
            if m:
                (left, mid, right) = m.groups()
                if re.match( mid, self.asyncid ):
                    newout = left + mg + right

                    del self.outputs.satisfied[ output ]
                    self.outputs.satisfied[ newout ] = False

        for deathpre in self.death_prerequisites.get_list():
            m = re.match( '^(.*)\((.*)\)(.*)', deathpre )
            if m:
                (left, mid, right) = m.groups()
                if re.match( mid, self.asyncid ):
                    newpre = left + mg + right

                    del self.death_prerequisites.satisfied[ deathpre ]
                    self.death_prerequisites.satisfied[ newpre ] = False

        # if task is asynchronous it has
        #  - used_outputs
        #  - loose prerequisites
        #  - death prerequisites

    def dump_state( self, FILE ):
        # Write state information to the state dump file
        # This must be compatible with __init__() on reload
        FILE.write( self.id + ' : ' + self.asyncid + ' | ' + self.state.dump() + '\n' )

    def satisfy_me( self, outputs ):
        self.prerequisites.satisfy_me( outputs, self.__class__.used_outputs.keys() )
        self.death_prerequisites.satisfy_me( outputs )
