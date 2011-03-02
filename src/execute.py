#!/usr/bin/env python

import sys, os

# subprocess.call() - if shell=True, command is string, not list.

def execute( command_list, ignore_output=False, notify=False ):

    try:
        import subprocess
        use_subprocess = True
    except:
        use_subprocess = False
        print "+++++++++++++++++++++++++++++++++++++++++++++++"
        print "WARNING: UNABLE TO IMPORT THE SUBPROCESS MODULE"
        pyver = sys.version_info
        if pyver < (2, 4):
            print "  (subprocess was introduced in Python 2.4)"
        print "Cylc will use os.system to invoke subprocesses,"
        print "but it cannot check for successful invocation."
        print "+++++++++++++++++++++++++++++++++++++++++++++++"
        print

    if use_subprocess:
        try:
            if ignore_output:
                # THIS BLOCKS UNTIL THE COMMAND COMPLETES
                retcode = subprocess.call( command_list, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT )
            else:
                # THIS BLOCKS UNTIL THE COMMAND COMPLETES
                retcode = subprocess.call( command_list )

            if retcode != 0:
                # the command returned non-zero exist status
                print >> sys.stderr, ' '.join( command_list ), ' failed: ', retcode
                sys.exit(1)
            else:
                if notify:
                    #print ' '.join( command_list ), ' succeeded'
                    print 'DONE'
                sys.exit(0)

        except OSError:
            # the command was not invoked
            print >> sys.stderr, 'ERROR: unable to execute ', ' '.join(command_list)
            #print >> sys.stderr, ' * Have you sourced $CYLC_DIR/cylc-env.sh?'
            #print >> sys.stderr, " * Are all cylc scripts executable?"
            sys.exit(1)
    else:
        command = ' '.join(command_list)
        #print "OS.SYSTEM: " + command
        os.system( command )
