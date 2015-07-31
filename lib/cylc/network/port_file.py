#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
from cylc.suite_host import is_remote_host
from cylc.owner import user, is_remote_user
from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags

"""At start-up the suite port number is written to ~/.cylc/ports/SUITE.

Task messaging commands get the suite port number from $CYLC_SUITE_PORT.
Other commands get the port number of the target suite from the port file.
"""


class PortFileError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class PortFileExistsError(PortFileError):
    pass


class PortFile(object):
    """Write, remember, and unlink a suite port file on localhost.

    """
    def __init__(self, suite, port):
        self.suite = suite
        # The ports directory is assumed to exist.
        pdir = GLOBAL_CFG.get(['pyro', 'ports directory'])
        self.local_path = os.path.join(pdir, suite)
        try:
            self.port = str(int(port))
        except ValueError, x:
            print >> sys.stderr, x
            raise PortFileError("ERROR, illegal port number: %s" % port)
        self.write()

    def write(self):
        if os.path.exists(self.local_path):
            raise PortFileExistsError(
                "ERROR, port file exists: %s" % self.local_path)
        try:
            f = open(self.local_path, 'w')
        except OSError:
            raise PortFileError(
                "ERROR, failed to open port file: %s " % self.port)
        f.write(self.port)
        f.close()

    def unlink(self):
        try:
            os.unlink(self.local_path)
        except OSError as exc:
            print >> sys.stderr, str(exc)
            raise PortFileError(
                "ERROR, failed to remove port file: %s" % self.local_path)


class PortRetriever(object):
    """Retrieve a suite port number from a port file (local or remote).

    """
    def __init__(self, suite, host, owner):
        self.suite = suite
        self.host = host
        self.owner = owner
        self.locn = None
        self.local_path = os.path.join(
            GLOBAL_CFG.get(['pyro', 'ports directory']), suite)

    def get_local(self):
        self.locn = self.local_path
        if not os.path.exists(self.local_path):
            raise PortFileError("Port file not found - suite not running?.")
        f = open(self.local_path, 'r')
        str_port = f.readline().rstrip('\n')
        f.close()
        return str_port

    def get_remote(self):
        import subprocess
        target = self.owner + '@' + self.host
        remote_path = self.local_path.replace(os.environ['HOME'], '$HOME')
        self.locn = target + ':' + remote_path
        ssh = subprocess.Popen(
            ['ssh', '-oBatchMode=yes', target, 'cat', remote_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        str_port = ssh.stdout.readline().rstrip('\n')
        err = ssh.stderr.readline()
        res = ssh.wait()
        if err:
            print >> sys.stderr, err.rstrip('\n')
        if res != 0:
            raise PortFileError("ERROR, remote port file not found")
        return str_port

    def get(self):
        if is_remote_host(self.host) or is_remote_user(self.owner):
            str_port = self.get_remote()
        else:
            str_port = self.get_local()
        try:
            port = int(str_port)
        except ValueError, x:
            # This also catches an empty port file (touch).
            print >> sys.stderr, x
            print >> sys.stderr, "ERROR: bad port file", self.locn
            raise PortFileError(
                "ERROR, illegal port file content: %s" % str_port)
        if cylc.flags.verbose:
            print "Suite port is", port
        return port
