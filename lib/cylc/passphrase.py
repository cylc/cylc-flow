#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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
from stat import *
import random
import string
from mkdir_p import mkdir_p
from hostname import hostname
from registration import dbgetter, RegistrationError


class SecurityError( Exception ):
    """
    Attributes:
        message - what the problem is.
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class PassphraseNotFoundError( SecurityError ):
    pass

class PassphraseNotReadableError( SecurityError ):
    pass

class InsecurePassphraseError( SecurityError ):
    pass

class InvalidPassphraseError( SecurityError ):
    pass

class passphrase(object):
    def __init__( self, suite, owner, host ):
        self.suite = suite
        self.owner = owner
        self.host = host

        ### ?? this doesn't matter, we now set permissions explicitly:
        ### ?? To Do: handle existing file that owner can't read? etc.?
        ##mode = os.stat( ppfile )[ST_MODE]
        ##if not S_IRUSR & mode:
        ##    raise PassphraseNotReadableError, 'Owner cannot read passphrase file: ' + ppfile
        ##if S_IROTH & mode or S_IWOTH & mode or S_IXOTH & mode:
        ##    raise InsecurePassphraseError, 'OTHERS have access to passphrase file: ' + ppfile
        ##if S_IRGRP & mode or S_IWGRP & mode or S_IXGRP & mode:
        ##    raise InsecurePassphraseError, 'GROUP has access to passphrase file: ' + ppfile
    def get_passphrase_file( self, dir=None ):
        """
Passphrase location, order of preference:

1/ The dir argument (this is used for initial passphrase creation by the
register command, and if the user specifies the location on the command
line.

2/ The suite definition directory, because suites may be automatically
installed (e.g. by Rose) to remote task hosts, and remote tasks know
this location from their execution environment. Local user command
invocations can use the suite registration database to find the suite
definition directory.  HOWEVER, remote user command invocations cannot
do this even if the local and remote hosts share a common filesystem,
because we cannot be sure if finding the expected suite registration
implies a common filesystem or a different remote suite that happens to
be registered under the same name. User accounts used for remote control
must therefore install the passphrase in the secondary standard location
(below) or use the command line option to explicitly reveal the
location.

3/ $HOME/.cylc/HOST/OWNER/SUITE/; this is a more sensible location for
enabling remote suite control from accounts that do not actually need
the suite definition directory to be installed. OWNER is the username 
of the suite owner on the suite HOST.

4/ $HOME/.cylc/SUITE/; this is simpler than 3/ if you are not concerned
about other suites with the same name."""

        location = None

        # 1/ input directory argument
        if dir:
            if not dir.endswith('passphrase'):
                pfile = os.path.join( dir, 'passphrase' )
            else:
                pfile = dir
            if os.path.isfile( pfile ):
                location = pfile
            else:
                # if an explicit location is given, the file must exist
                raise SecurityError, 'ERROR: suite passphrase not found in ' + dir

        # 2/ suite definition directory
        if not location:
            # 2(i) check environment (for remote tasks)
            try:
                pfile = os.path.join( os.environ['CYLC_SUITE_DEF_PATH'], 'passphrase' )
            except KeyError:
                pass
            else:
                if os.path.isfile( pfile ):
                    location = pfile

        if not location and os.environ['USER'] == self.owner and self.host == hostname:
            # 2(ii) check registration (for the local suite owner only)
            dbg = dbgetter()
            try:
                suite, suiterc = dbg.get_suite(self.suite)
            except RegistrationError, x:
                pass
            else:
                pfile = os.path.join( os.path.dirname(suiterc), 'passphrase' )
                if os.path.isfile( pfile ):
                    location = pfile

        # check under .cylc/HOST/OWNER/SUITE
        if not location:
            pfile = os.path.join( os.environ['HOME'], '.cylc', self.host, self.owner, self.suite, 'passphrase' )
            if os.path.isfile( pfile ):
                location = pfile

        # check under .cylc/SUITE
        if not location:
            pfile = os.path.join( os.environ['HOME'], '.cylc', self.suite, 'passphrase' )
            if os.path.isfile( pfile ):
                location = pfile

        if not location:
            raise SecurityError, 'ERROR: suite passphrase not found.'
        else:
            # set passphrase file permissions to owner-only
            os.chmod( location, 0600 )
            return location

    def generate( self, dir ):
        pfile = os.path.join(dir, 'passphrase')
        if os.path.isfile( pfile ):
            print "\nThis suite has an existing passphrase.\n"
            return
        char_set = string.ascii_uppercase + string.ascii_lowercase + string.digits
        self.passphrase = ''.join(random.sample(char_set,20))
        mkdir_p(dir)
        f = open(os.path.join(dir, 'passphrase'), 'w')
        f.write(self.passphrase)
        f.close()
        print """
________________________________________________________________________
A new random passphrase has been generated for this suite:\n   """, pfile, """
It must be distributed to any other user accounts (local or remote)
that host this suite's tasks, and similarly to any user accounts from
which cylc commands will be used to connect to the running suite. 

Cylc's remote task messaging commands will look for the passphrase at 
$CYLC_SUITE_DEF_PATH/passphrase; if not found there (e.g. if the suite
definition is not installed on a remote task host) they will look in
$HOME/.cylc/SUITE_HOST/SUITE_OWNER/SUITE/passphrase; and then in
$HOME/.cylc/SUITE/passphrase. The latter locations are convenient for
remote suite control, in which case the suite definition directory will
not be known; finally, you can specify the location on the commandline.
------------------------------------------------------------------------
"""

    def get( self, dir=None ):
        ppfile = self.get_passphrase_file( dir )
        psf = open( ppfile, 'r' )
        lines = psf.readlines()
        psf.close()
        if len(lines) != 1:
            raise InvalidPassphraseError, 'Passphrase file contains multiple lines: ' + ppfile
        line0 = lines[0]
        # chomp trailing whitespace and newline
        self.passphrase = re.sub( '\s*\n', '', line0 )
        return self.passphrase

