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

#_______________________________________________________________________
#            THIS IS THE CYLC SUITE.RC SPECIFICATION FILE
#-----------------------------------------------------------------------
# Entries are documented in suite.rc reference in the Cylc User Guide. 

# _________________________________________________________MAIN SECTIONS
# [cylc]          - non task-related suite config.
# [scheduling]    - determines when tasks are ready to run.
# [runtime]       - how, where, what to execute when a task is ready.
# [visualization] - for suite graphing and the gcontrol graph view.

#_______________________________________________________________________
# WARNING: a CONFIGOBJ or VALIDATE bug? list constructor fails if final
# element is followed by a space (or does it just need a trailing comma?):
#   GOOD: foo = string_list( default=list('foo','bar'))
#   BAD:  bar = string_list( default=list('foo','bar' ))

#___________________________________________________________________HEAD
title = string( default="No title provided" )
description = string( default="No description provided" )

