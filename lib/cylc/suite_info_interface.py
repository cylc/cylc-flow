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

import copy
import sys, os
import Pyro.core
from CylcError import TaskNotFoundError, TaskStateError
from job_submission.job_submit import job_submit
from version import cylc_version
from owner import user

"""Pyro interface for DIRECT READ-ONLY INTERACTION with a cylc suite.
Any interaction that alters suite state in any way must go via the
indirect thread-safe suite command interface queue."""

#class result:
#    """TODO - GET RID OF THIS - ONLY USED BY INFO COMMANDS"""
#    def __init__( self, success, reason="Action succeeded", value=None ):
#        self.success = success
#        self.reason = reason
#        self.value = value

class info_interface( Pyro.core.ObjBase ):
    def __init__( self, info_commands ):
        Pyro.core.ObjBase.__init__(self)
        self.commands = info_commands

    def get( self, descrip, *args ):
#        # TODO - HOW WHAT TO RETURN IN CASE OF UNKNOWN COMMAND
#        if descrip not in self.commands:
#            return result( False, reason="Unknown command" )
        return self.commands[ descrip ]( *args )

