#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
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

# A minimal Pyro-connected object to allow client programs to identify
# what suite is running at a given cylc port - by suite name and owner.

# All *other* suite objects should be connected to Pyro via qualified
# names: owner.suite.object, to prevent accidental access to the wrong
# suite. This object, however, should be connected unqualified so that
# that same ID method can be called on any active cylc port.

import Pyro.core

class identifier( Pyro.core.ObjBase ):
    def __init__( self, name, owner ):
        self.owner = owner
        self.name = name
        Pyro.core.ObjBase.__init__( self )

    def id( self ):
        return ( self.name, self.owner )
