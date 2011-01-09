#!/usr/bin/python

import subprocess
import datetime

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

    print 'SRT:', datetime.datetime.now()

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

    print 'END:', datetime.datetime.now()
