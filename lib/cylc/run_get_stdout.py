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

import sys
import subprocess

def run_get_stdout( command ):
    try:
        popen = subprocess.Popen( command, shell=True,
                stderr=subprocess.PIPE, stdout=subprocess.PIPE )
        out = popen.stdout.read()
        err = popen.stderr.read()
        res = popen.wait()
        if res < 0:
            msg = "ERROR: command terminated by signal %d\n%s" % (res, err)
            return (False, [msg,command])
        elif res > 0:
            msg = "ERROR: command failed %d\n%s" % (res,err)
            return (False, [msg, command])
    except OSError, e:
        msg = "ERROR: command invocation failed"
        return (False, [msg, command])
    else:
        # output is a string with newlines
        res = (out + err ).strip()
        return ( True, res.split('\n') )

