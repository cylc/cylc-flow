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

from cylc.version import cylc_version

"""
Defines a string of scripting that sets CYLC_VERSION prior to sourcing
profile scripts. It is used at the top of task job scripts to give tasks
access to cylc on task hosts; and as the first part of event handler and
task poll and kill command strings, so that those commands also run
under the selected cylc version (event handlers may call cylc commands).
This allows users to run suites under multiple cylc versions at once, by 
setting their $PATH according to the cylc version number if necessary.
"""

cv_export = "export CYLC_VERSION=" + cylc_version

s_profile = [
    "test -f /etc/profile && . /etc/profile 1>/dev/null 2>&1",
    "test -f $HOME/.profile && . $HOME/.profile 1>/dev/null 2>&1"
            ]

# single line profile scripting:
pr_scripting_sl = '; '.join(s_profile)

# single line cylc version scripting:
cv_scripting_sl = cv_export + '; ' + '; '.join(s_profile)

# multi line cylc version scripting:
cv_scripting_ml = """
""" + cv_export + """
""" + '\n'.join( s_profile )

