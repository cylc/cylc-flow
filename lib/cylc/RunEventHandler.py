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

import subprocess
import logging

def RunHandler( event, script, suite, taskID=None, msg=None, fg=False ):
    """This is now only used for suite (not task) event handlers."""

    tolog = 'Calling ' + event + ' handler'
    if fg:
        tolog += ' in the foreground'
    print tolog
    logger = logging.getLogger('main')
    logger.info( tolog )
    command = script + ' ' + event + ' ' + suite
    if taskID:
        command += ' ' + taskID
    command += " '" + msg + "'"
    if not fg:
        command += ' &'

    res = subprocess.call( command, shell=True )
    if fg and res != 0:
        raise Exception( 'ERROR: event handler failed' )
