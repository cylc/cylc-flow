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

import os, sys
import subprocess
from textwrap import TextWrapper
from pipes import quote
from suite_owner import username

class remrun( object ):
    """If owner or host differ from username and localhost, strip the
    remote options from the commandline and reinvoke the command on the
    remote host by passwordless ssh, then exit; else do nothing."""
    # To ensure that users are aware of remote re-invocation info is 
    # always printed, but to stderr so as not to interfere with results.

    def __init__( self ):
        self.owner = username
        self.host = 'localhost'
        self.ssh_login_shell = True

        if '-v' in sys.argv or '--verbose' in sys.argv:
            self.verbose = True
        else:
            self.verbose = False

        argv = sys.argv[1:]
        self.args = []
        # detect and replace host and owner options
        while argv:
            arg = argv.pop(0)
            if arg.startswith("--owner="):
                self.owner = arg.replace("--owner=", "")
            elif arg.startswith("--host="):
                self.host = arg.replace("--host=", "")
            elif arg == "--login":
                self.ssh_login_shell = True
            elif arg == "--no-login":
                self.ssh_login_shell = False
            else:
                self.args.append(arg)

    def execute( self, force_required=False, env={}, path=[] ):
        # returns False if remote re-invocation is not needed,
        # True it is is needed and executes successfully
        # otherwise aborts.
        if self.owner == username and self.host == 'localhost':
            return False

        if force_required and \
                '-f' not in sys.argv[1:] and '--force' not in sys.argv[1:]:
                    sys.exit("ERROR: force (-f) required for non-interactive command invocation.")

        name = os.path.basename(sys.argv[0])[5:] # /path/to/cylc-foo => foo

        user_at_host = ''
        if self.owner: 
            user_at_host = self.owner  + '@'
        if self.host:
            user_at_host += self.host
        else:
            user_at_host += 'localhost'

        # Build the remote command
        command = []
        if self.ssh_login_shell:
            # A login shell will always source /etc/profile and the user's bash profile file.
            # To avoid having to quote the entire remote command it is passed as arguments to
            # the bash script.
            command += ["bash","--login","-c","'$0 \"$@\"'"]
        if path != []:
            remote_cylc_command = '/'.join(path+["cylc"])
        else:
            remote_cylc_command = "cylc"
        command += [remote_cylc_command, name]
        for var,val in env.iteritems():
            command += ["--env=%s=%s"%(var,val)]
        for arg in self.args:
            command += ["'"+arg+"'"]
            # above: args quoted to avoid interpretation by the shell, 
            # e.g. for match patterns such as '.*' on the command line.

        # ssh command and options (X forwarding)
        command = ["ssh", "-oBatchMode=yes", "-Y", user_at_host] + command

        print "Remote command re-invocation for", user_at_host
        if self.verbose:
            # Wordwrap the command, quoting arguments so they can be run
            # properly from the command line
            print '\n'.join(TextWrapper(subsequent_indent='\t').wrap(' '.join(map(quote,command))))

        try:
            popen = subprocess.Popen( command )
            res = popen.wait()
            if res < 0:
                sys.exit("ERROR: remote command terminated by signal %d" % res)
            elif res > 0:
                sys.exit("ERROR: remote command failed %d" % res)
        except OSError, e:
            sys.exit("ERROR: remote command invocation failed %s" % str(e))
        else:
            print "Remote command re-invocation done"
            return True

