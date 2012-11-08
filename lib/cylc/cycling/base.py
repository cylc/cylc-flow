#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

class CyclerError( Exception ):
    pass

class CyclerOverrideError( CyclerError ):
    def __init__( self, method_name ):
        self.meth = method_name
    def __str__( self ):
        return repr("ERROR: derived classes must override cycler." + self.meth + "()" )

class cycler( object ):
    """Defines the interface that derived classes implement in order for
    cylc to generate tasks with a particular sequence of cycle times.
    
    NOTE: in method arguments and return values below: 
    * T represents a cycle time in string form (YYYYMMDDHHmmss)
    * CT represents a cycle_time.ct(T) object

    We will eventually use cycle time objects throughout cylc,
    extracting the string form from the object only when necessary."""

    @classmethod
    def offset( cls, T, n ):
        """Decrement the cycle time T by the integer n (which may be
        negative, implying an increment - this can be used in offset
        internal task output messages), where the units of n (e.g.
        days or years) are defined by the derived class. This is a class
        method because a time offset T-n does not depend on the details
        of the sequence, other than the units."""
        raise CyclerOverrideError( "offset" )

    def __init__( self, *args ):
        """Initialize a cycler object. The number and type of arguments,
        and stored object data, depends on the derived cycler class."""
        raise CyclerOverrideError( "__init__" )

    def valid( self, CT ):
        """Return True or False according to whether or not CT is a
        valid member of the cycler's sequence of cycle times."""
        raise CyclerOverrideError( "valid" )

    def initial_adjust_up( self, T ):
        """Return T adjusted up, if necessary, to the nearest subsequent
        cycle time valid for this cycler. This method is used at suite
        start-up to find the first valid cycle at or after the suite
        initial cycle time; subsequently next() ensures we stay valid."""
        raise CyclerOverrideError( "initial_adjust_up" )

    def next( self, T ):
        """Return the cycle time next in the sequence after T. It may 
        be assumed that T is already on sequence."""
        raise CyclerOverrideError( "next" )

    def get_min_cycling_interval( self ):
        """Return the smallest cycling interval for this cycler.""" 
        raise CyclerOverrideError( "get_min_cycling_interval" )

    def adjust_state( self, offset ):
        """Adjust the state variables that define the cycle time sequence
        to offset the whole sequence. This is used for tasks on the left 
        of intercycle triggers, e.g. in "A[T-6] => B" implies that task A 
        runs at cycles 6 hours prior to the cycler sequence."""
        raise CyclerOverrideError( "adjust_state" )
