#!/usr/bin/python

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
from cylc.wallclock import get_current_time_string


class multisubprocess:
    def __init__( self, commandlist, shell=True ):
        self.shell = shell
        self.commandlist = commandlist

    def execute( self ):
        procs = []
        for command in self.commandlist:
            proc = subprocess.Popen( command, shell=self.shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
            procs.append( proc )

        out = []
        err = []
        for proc in procs:
            o, e = proc.communicate()
            out.append(o)
            err.append(e)

        return ( out, err )

if __name__ == "__main__":
    commands = []
    for i in range(1,5):
        if i == 4:
            command = "echoX hello from " + str(i) + "; sleep 10; echo bye from " + str(i)
        else:
            command = "echo hello from " + str(i) + "; sleep 10; echo bye from " + str(i)

        commands.append( command )

    print 'SRT:', get_current_time_string(display_sub_seconds=True)

    mp = multisubprocess( commands )
    out, err = mp.execute()

    count = 1
    for item in out:
        print count
        print item
        count += 1

    count = 1
    for item in err:
        print count
        print item
        count += 1

    print 'END:', get_current_time_string(display_sub_seconds=True)
