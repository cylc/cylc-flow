#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

# NOTE on conditional and non-conditional triggers: all plain triggers
# (for a single task) are held in a single prerequisite object; but one
# such object is held for each conditional trigger. This has
# implications for global detection of duplicated prerequisites
# (detection is currently disabled).

import sys, re, os
from prerequisites.prerequisites import prerequisites
from prerequisites.plain_prerequisites import plain_prerequisites
from prerequisites.conditionals import conditional_prerequisites
from task_output_logs import logfiles
from outputs import outputs
import TaskID
from task_output_logs import logfiles
from parsec.OrderedDict import OrderedDict
from cycling.loader import get_interval_cls, get_point_relative, get_interval


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

    def __init__( self, name, rtcfg, run_mode, ict ):
        if re.search( '[^0-9a-zA-Z_\.]', name ):
            # dot for namespace syntax (NOT USED).
            # regex [\w] allows spaces.
            raise DefinitionError, "ERROR: Illegal task name: " + name

        self.run_mode = run_mode
        self.rtconfig = rtcfg
        self.ict = ict

        self.sequences = []
        self.implicit_sequences = []  # Implicit sequences are deprecated.

        # some defaults
        self.intercycle = False
        self.max_future_prereq_offset = None
        self.intercycle_offsets = []
        self.sequential = False
        self.cycling = False
        self.modifiers = []
        self.is_coldstart = False
        self.suite_polling_cfg = {}

        self.follow_on_task = None
        self.clocktriggered_offset = None
        self.namespace_hierarchy = []
        # triggers[0,6] = [ A, B:1, C(T-6), ... ]
        self.triggers = {}
        # cond[6,18] = [ '(A & B)|C', 'C | D | E', ... ]
        self.cond_triggers = {}
        self.outputs = [] # list of explicit internal outputs; change to dict if need to vary per cycle.

        self.name = name
        self.type = 'cycling'

    def add_trigger( self, trigger, sequence ):
        if sequence not in self.triggers:
            self.triggers[ sequence ] = []
        self.triggers[sequence].append(trigger)

    def add_conditional_trigger( self, triggers, exp, sequence ):
        if sequence not in self.cond_triggers:
            self.cond_triggers[ sequence ] = []
        self.cond_triggers[ sequence ].append( [triggers,exp] )

    def add_sequence( self, sequence, is_implicit=False ):
        # TODO ISO - SEQUENCES CAN BE HELD BY TASK CLASS NOT INSTANCE
        if sequence not in self.sequences:
            self.sequences.append( sequence )
            if is_implicit:
                self.implicit_sequences.append( sequence )

    def get_cleanup_cutoff_point( self, my_point, offset_sequence_tuples):
        """Extract the max dependent cycle point for this point."""
        print "Extract cleanup cutoff", self.name, my_point
        if not offset_sequence_tuples:
            print "    not offset_seq_tuples: None"
            return None
        cutoff_points = []
        for offset_string, sequence in offset_sequence_tuples:
            print "    offset_string, sequence", offset_string, str(sequence)
            if offset_string is None:
                # This indicates a dependency across the whole suite run.
                return None
            if sequence is None:
                cutoff_points.append(
                    my_point - get_interval(offset_string))
                print "        cutoff point candidate:", cutoff_points[-1]
                continue
            dependent_point = sequence.get_start_point()
            
            matching_dependent_points = []
            while dependent_point is not None:
                target_point = (
                    get_point_relative(offset_string, dependent_point))
                print "    dependent, target:", dependent_point, target_point
                if target_point > my_point:
                    # Assume monotonic (target_point can never jump back).
                    break
                if target_point == my_point:
                    matching_dependent_points.append(dependent_point)
                    print "        cutoff point candidate:", dependent_point
                dependent_point = sequence.get_next_point_on_sequence(
                    dependent_point)
            if matching_dependent_points:
                # Choose the largest of the dependent points.
                cutoff_points.append(matching_dependent_points[-1])
        if cutoff_points:
            max_cutoff_point = max(cutoff_points)
            print "    cutoff max:", max_cutoff_point
            if max_cutoff_point < my_point:
                print "    too low, defaulting to:", my_point
                return my_point
            return max_cutoff_point
        print "    no cutoff points:", None
        return None
                
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
                return float(hrs)
            else:
                return float(hrs)*60.0

    def get_task_class( self ):
        # return a task proxy class definition, to be used for
        # instantiating objects of this particular task class.
        base_types = []
        for foo in self.modifiers + [self.type]:
            mod = __import__( 'cylc.task_types.' + foo, fromlist=[foo] )
            base_types.append( getattr( mod, foo ) )

        tclass = type( self.name, tuple( base_types), dict())

        # set class variables here
        tclass.title = self.rtconfig['title']
        tclass.description = self.rtconfig['description']

        # For any instance-specific environment variables (note that
        # [runtime][TASK][enviroment] is now held in a class variable).
        tclass.env_vars = OrderedDict()

        tclass.name = self.name        # TODO - NOT NEEDED, USED class.__name__

        tclass.rtconfig = self.rtconfig
        tclass.run_mode = self.run_mode

        tclass.elapsed_times = []
        tclass.mean_total_elapsed_time = None

        tclass.intercycle = self.intercycle
        tclass.max_future_prereq_offset = None
        tclass.follow_on = self.follow_on_task

        tclass.namespace_hierarchy = self.namespace_hierarchy

        def tclass_add_prerequisites( sself, point  ):
            # NOTE: Task objects hold all triggers defined for the task
            # in all cycling graph sections in this data structure:
            #     self.triggers[sequence] = [list of triggers for this
            #     sequence]
            # The list of triggers associated with sequenceX will only be
            # used by a particular task if the task's cycle point is a
            # valid member of sequenceX's sequence of cycle points.

            # 1) non-conditional triggers
            pp = plain_prerequisites( sself.id, self.ict )
            sp = plain_prerequisites( sself.id, self.ict )

            if self.sequential:
                # For tasks declared 'sequential' we automatically add a
                # previous-instance inter-cycle trigger, and adjust the
                # cleanup cutoff (determined by inter-cycle triggers)
                # accordingly.

                p_next = None
                adjusted = []
                for seq in self.sequences:
                    nxt = seq.get_next_point(sself.point)
                    if nxt:
                        # may be None if beyond the sequence bounds
                        adjusted.append( nxt )
                if adjusted:
                    p_next = min( adjusted )
                    if (sself.cleanup_cutoff is not None and
                            sself.cleanup_cutoff < p_next):
                        sself.cleanup_cutoff = p_next
                else:
                    # TODO ISO - ??
                    pass

                p_prev = None
                adjusted = []
                for seq in self.sequences:
                    prv = seq.get_nearest_prev_point(sself.point)
                    if prv:
                        # may be None if out of sequence bounds
                        adjusted.append( prv )
                if adjusted:
                    p_prev = max( adjusted )
                    pp.add( TaskID.get( sself.name, str(p_prev) ) + ' succeeded' )
                else:
                    # TODO ISO - ??
                    pass

            for sequence in self.triggers:
                for trig in self.triggers[ sequence ]:
                    if trig.cycling and not sequence.is_valid( sself.point ):
                        # This trigger is not used in current cycle
                        continue
                    if (self.ict is None or
                            trig.evaluation_offset_string is None or
                            (get_point_relative(
                                trig.evaluation_offset_string, point) >=
                             self.ict)):
                        # i.c.t. can be None after a restart, if one
                        # is not specified in the suite definition.

                        message, prereq_point = trig.get( point )
                        prereq_offset = prereq_point - point
                        if (prereq_offset > get_interval_cls().get_null() and
                                (sself.max_future_prereq_offset is None or
                                 prereq_offset >
                                 sself.max_future_prereq_offset)):
                            sself.max_future_prereq_offset = prereq_offset

                        if trig.suicide:
                            sp.add( message )
                        else:
                            pp.add( message )

            sself.prerequisites.add_requisites( pp )
            sself.suicide_prerequisites.add_requisites( sp )

            # 2) conditional triggers
            for sequence in self.cond_triggers.keys():
                for ctrig, exp in self.cond_triggers[ sequence ]:
                    foo = ctrig.keys()[0]
                    if (ctrig[foo].cycling and
                            not sequence.is_valid( sself.point)):
                        # This trigger is not valid for current cycle (see NOTE just above)
                        continue
                    cp = conditional_prerequisites( sself.id, self.ict )
                    for label in ctrig:
                        trig = ctrig[label]
                        if (self.ict is not None and
                                trig.evaluation_offset_string is not None):
                            is_less_than_ict = (
                                get_point_relative(
                                    trig.evaluation_offset_string, point) <
                                self.ict
                            )
                            cp.add( trig.get( point )[0], label,
                                    is_less_than_ict)
                        else:
                            cp.add( trig.get( point )[0], label )
                    cp.set_condition( exp )
                    if ctrig[foo].suicide:
                        sself.suicide_prerequisites.add_requisites( cp )
                    else:
                        sself.prerequisites.add_requisites( cp )

        tclass.add_prerequisites = tclass_add_prerequisites

        # class init function
        def tclass_init( sself, start_point, initial_state, stop_point=None,
                         startup=False, validate=False, submit_num=0,
                         exists=False ):

            sself.sequences = self.sequences
            sself.implicit_sequences = self.implicit_sequences
            sself.startup = startup
            sself.submit_num = submit_num
            sself.exists=exists
            sself.intercycle_offsets = self.intercycle_offsets

            if self.cycling and startup:
                # adjust up to the first on-sequence cycle point
                adjusted = []
                for seq in sself.sequences:
                    adj = seq.get_first_point( start_point )
                    if adj:
                        # may be None if out of sequence bounds
                        adjusted.append( adj )
                if adjusted:
                    sself.point = min( adjusted )
                    sself.cleanup_cutoff = self.get_cleanup_cutoff_point(
                        sself.point, self.intercycle_offsets)
                    sself.id = TaskID.get( sself.name, str(sself.point) )
                else:
                    sself.point = None
                    # this task is out of sequence bounds (caller much
                    # check for a point of None)
                    return
            else:
                sself.point = start_point
                sself.cleanup_cutoff = self.get_cleanup_cutoff_point(
                    sself.point, self.intercycle_offsets)
                sself.id = TaskID.get( sself.name, str(sself.point) )

            if 'clocktriggered' in self.modifiers:
                sself.real_time_delay =  float( self.clocktriggered_offset )

            # prerequisites
            sself.prerequisites = prerequisites( self.ict )
            sself.suicide_prerequisites = prerequisites( self.ict )
            sself.add_prerequisites( sself.point )

            sself.logfiles = logfiles()
            for lfile in self.rtconfig[ 'extra log files' ]:
                sself.logfiles.add_path( lfile )

            # outputs
            sself.outputs = outputs( sself.id )
            for outp in self.outputs:
                msg = outp.get( sself.point )
                if not sself.outputs.exists( msg ):
                    sself.outputs.add( msg )
            sself.outputs.register()

            if stop_point:
                # cycling tasks with a final cycle point set
                super( sself.__class__, sself ).__init__(
                    initial_state, stop_point, validate=validate )
            else:
                # TODO ISO - is this OK for vanished Async tasks?
                sself.stop_point = None
                super( sself.__class__, sself ).__init__( initial_state, validate=validate )

            sself.suite_polling_cfg = self.suite_polling_cfg
            sself.reconfigure_me = False
            sself.is_coldstart = self.is_coldstart
            sself.set_from_rtconfig()

        tclass.__init__ = tclass_init

        return tclass

