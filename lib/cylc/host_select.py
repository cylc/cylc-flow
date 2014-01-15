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

import os, re
from cylc.run_get_stdout import run_get_stdout

def get_task_host( cfg_item ):
    """
    Evaluate a host-selection command or environment variable, if
    present, or else return the original explicit hostname.

    [runtime]
        [[NAME]]
            [[[remote]]]
                host = cfg_item

    cfg_item may be an explicit host name, a command in back-tick or
    $(command) format, or an environment variable holding a hostname.
    """

    host = cfg_item

    if not host:
        return host

    # 1) host selection command: $(command) or `command`
    m = re.match( '(`|\$\()\s*(.*)\s*(`|\))$', host )
    if m:
        # extract the command and execute it
        hs_command = m.groups()[1]
        res = run_get_stdout( hs_command ) # (T/F,[lines])
        if res[0]:
            # host selection command succeeded
            host = res[1][0]
        else:
            # host selection command failed
            raise Exception("Host selection by " + host + " failed\n  " + '\n'.join(res[1]) )

    # 2) environment variable: ${VAR} or $VAR
    # (any quotes are stripped by file parsing) 
    n = re.match( '^\$\{{0,1}(\w+)\}{0,1}$', host )
    if n:
        var = n.groups()[0]
        try:
            host = os.environ[var]
        except KeyError, x:
            raise Exception( "Host selection by " + host + " failed:\n  Variable not defined: " + str(x) )

    return host

