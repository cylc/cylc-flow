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

from background import background

class background_slow( background ):
    """
This is a deliberately slow version of background job submission, used
for cylc development purposes - sleep for a while before executing the task.

Change sleep time by setting $CYLC_BG_SLOW_SLEEP in [cylc][[environment]]
(or in the terminal environment before running the suite).
    """
    # stdin redirection (< /dev/null) allows background execution
    # even on a remote host - ssh can exit without waiting for the
    # remote process to finish.

    COMMAND_TEMPLATE = "sleep ${CYLC_BG_SLOW_SLEEP:-60}; %s </dev/null 1>%s 2>%s &"

