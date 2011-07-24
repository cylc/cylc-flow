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

import sys, re
from task import task
from nopid import nopid

class asynchronous( nopid, task ):
    # a non-cycling task with no previous instance dependence (so it
    # spawns when it first enters the running state).

    is_asynchronous = True

    used_outputs = {}
    
    def __init__( self, state ):
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

        task.__init__( self, state )

    #def nearest_c_time( self, c_time ):
    #    # !TEMPORARY HACK!
    #    return c_time

    def next_tag( self ):
        return str( int( self.tag ) + 1 )

    def check_requisites( self ):
        print '\n________________>'
        print 'pre: ', self.id, self.death_prerequisites.dump()
        for message in self.prerequisites.labels:
            lbl = self.prerequisites.labels[message]
            if not self.prerequisites.satisfied[lbl]:
                continue
            # now looping over satisfied prerequisites

            # record which outputs already used by this task type
            self.__class__.used_outputs[ message ] = True

            # get the match group from this message
            mg = self.prerequisites.match_group[ message ]

            # propagate the match group into my outputs and death pre's
            for output in self.outputs.not_completed:
                m = re.match( '^(.*)\((.*)\)(.*)', output )
                if m:
                    (left, mid, right) = m.groups()
                    newout = left + mg + right

                    oid = self.outputs.not_completed[ output ] 
                    del self.outputs.not_completed[ output ]
                    self.outputs.not_completed[ newout ] = oid

                    self.env_vars[ 'ASYNCID' ] = mg 
                    self.asyncid = mg


            #print '\nXXXXXXXXXXXXxxxx'
            for deathpre in self.death_prerequisites.labels.keys():
                lbl = self.death_prerequisites.labels[deathpre]
                m = re.match( '^(.*)\((.*)\)(.*)', deathpre )
                #print deathpre
                if m:
                    #print 'XXXXXXMATCH!!!!!!!!!!!!!1111'

                    (left, mid, right) = m.groups()
                    newpre = left + mg + right

                    self.death_prerequisites.messages[lbl] = newpre
                    self.death_prerequisites.labels[newpre] = lbl
                    del self.death_prerequisites.labels[deathpre]
        print 'post: ', self.id, self.death_prerequisites.dump()

    def set_requisites( self ):
        # ONLY REQUIRED FOR RESTART?
        # UPDATE THIS METHOD!
        pass
        #mg = self.asyncid
        #for pre in self.prerequisites.get_list():
        #    m = re.match( '^(.*)\((.*)\)(.*)', pre )
        #    if m:
        #        (left, mid, right) = m.groups()
        #        if re.match( mid, self.asyncid ):
        #            newpre = left + mg + right
#
#                    del self.prerequisites.satisfied[ pre ]
#                    self.prerequisites.satisfied[ newpre ] = False
#                    self.__class__.used_outputs[ newpre ] = True
#
#        for output in self.outputs.get_list():
#            m = re.match( '^(.*)\((.*)\)(.*)', output )
#            if m:
#                (left, mid, right) = m.groups()
#                if re.match( mid, self.asyncid ):
#                    newout = left + mg + right
#
#                    del self.outputs.satisfied[ output ]
#                    self.outputs.satisfied[ newout ] = False
#
#        for deathpre in self.death_prerequisites.get_list():
#            m = re.match( '^(.*)\((.*)\)(.*)', deathpre )
#            if m:
#                (left, mid, right) = m.groups()
#                if re.match( mid, self.asyncid ):
#                    newpre = left + mg + right
#
#                    del self.death_prerequisites.satisfied[ deathpre ]
#                    self.death_prerequisites.satisfied[ newpre ] = False

        # if task is asynchronous it has
        #  - used_outputs
        #  - loose prerequisites
        #  - death prerequisites

    def dump_state( self, FILE ):
        # Write state information to the state dump file
        # This must be compatible with __init__() on reload
        FILE.write( self.id + ' (' + self.asyncid + ') : ' + self.state.dump() + '\n' )

    def satisfy_me( self, outputs ):
        self.prerequisites.satisfy_me( outputs, self.__class__.used_outputs.keys() )
        #print '\n_________________________'
        #print self.death_prerequisites.dump()
        #print self.outputs.dump()
        print 'SATIS: ', self.id, self.death_prerequisites.dump()
        self.death_prerequisites.satisfy_me_verbose( outputs )

    def get_state_summary( self ):
        summary = task.get_state_summary( self )
        summary[ 'asyncid' ] = self.asyncid
        return summary
