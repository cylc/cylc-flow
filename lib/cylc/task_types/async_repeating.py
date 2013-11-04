#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

class async_repeating( nopid, task ):
    """ A repeating asynchronous (no cycle time) task for use in
    processing satellite data or similar. Its prerequisites contain
    a pattern to match the "satellite pass ID" (which is essentially
    arbitrary but must uniquely identify any associated data sets).
    When matched, the prerequisite is satisfied, the matching ID is 
    passed to the external task as $ASYNCID (so that it can process
    the pass data) and substituted for <ASYNCID> in its own output
    messages in order that the ID can be passed on to downstream 
    tasks in the same way. The task type has no previous instance
    dependence: it spawns when it first enters the running state,
    to allow parallel processing of successive passes."""

    used_outputs = {}
    
    def __init__( self, state, validate = False ):
        # Call this AFTER derived class initialisation.
        # Top level derived classes must define self.id.
        self.env_vars['ASYNCID'] = 'UNSET'

        m = re.match( '(.*) \| (.*)', state )
        if m:
            # loading from state dump
            ( self.asyncid, state ) = m.groups()
            self.set_requisites()
            if re.search( 'running', state ):
                self.prerequisites.set_all_satisfied()
        else:
            self.asyncid = 'UNSET'
        self.env_vars[ 'ASYNCID' ] = self.asyncid 
        task.__init__( self, state, validate )

    def check_requisites( self ):
        for reqs in self.prerequisites.container:
            if not hasattr( reqs, 'is_loose' ):
                continue

            for message in reqs.labels:
                lbl = reqs.labels[message]
                if not reqs.satisfied[lbl]:
                    continue
                # now looping over satisfied prerequisites

                # record which outputs already used by this task type
                self.__class__.used_outputs[ message ] = True

                # get the match group from this message
                mg = reqs.asyncid

                # propagate the match group into my outputs
                for output in self.outputs.not_completed:
                    m = re.match( '^(.*)<ASYNCID>(.*)', output )
                    if m:
                        (left, right) = m.groups()
                        newout = left + mg + right
                        oid = self.outputs.not_completed[ output ] 
                        del self.outputs.not_completed[ output ]
                        self.outputs.not_completed[ newout ] = oid

                        self.env_vars[ 'ASYNCID' ] = mg 
                        self.asyncid = mg
                        break

    def set_requisites( self ):
        # On reload from state dump, replace match patterns with literal strings.
        mg = self.asyncid
        # ... in prerequisites:
        for reqs in self.prerequisites.container:
            if not hasattr( reqs, 'is_loose' ):
                continue
            for pre in reqs.labels.keys(): 
                m = re.match( '^(.*)<ASYNCID>(.*)', pre )
                if m:
                    (left, right) = m.groups()
                    newpre = left + mg + right
                    lbl = reqs.labels[pre]
                    reqs.labels[newpre] = lbl
                    del reqs.labels[pre]
                    reqs.messages[lbl] = newpre
                    reqs.asyncid = mg

        # ... in outputs:
        for output in self.outputs.completed.keys():
            m = re.match( '^(.*)<ASYNCID>(.*)', output )
            if m:
                (left, right) = m.groups()
                newout = left + mg + right
                del self.outputs.completed[ output ]
                self.outputs.completed[ newout ] = self.id

        for output in self.outputs.not_completed.keys():
            m = re.match( '^(.*)<ASYNCID>(.*)', output )
            if m:
                (left, right) = m.groups()
                newout = left + mg + right
                del self.outputs.not_completed[ output ]
                self.outputs.not_completed[ newout ] = self.id

    def dump_state( self, FILE ):
        # Write state information to the state dump file
        # This must be compatible with __init__() on reloading from state dump
        # and with load_state() format in bin/_restart.
        FILE.write( self.id +  ' : ' + self.asyncid + ' | ' +  self.state.dump() + '\n' )

    def satisfy_me( self, outputs ):
        # weed used-already outputs from outputs, so they're not re-used.
        woutputs = {}
        for out in outputs:
            if out not in self.__class__.used_outputs:
                woutputs[out] = outputs[out]
        self.prerequisites.satisfy_me( woutputs )

    def get_state_summary( self ):
        summary = task.get_state_summary( self )
        summary[ 'asyncid' ] = self.asyncid
        return summary

