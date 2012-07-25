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

import os
from stat import *
import random
import string
from mkdir_p import mkdir_p
from hostname import is_remote_host

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

    def get_passphrase_file( self, pfile=None, suiterc=None ):
        """
Passphrase location, order of preference:

1/ The pfile argument (used for initial passphrase creation by the
register command, and optionally on the command line.

2/ The suite definition directory, because suites may be automatically
installed (e.g. by Rose) to remote task hosts, and remote tasks know
this location from their execution environment. Local user command
invocations can use the suite registration database to find the suite
definition directory.  HOWEVER, remote user command invocations cannot
do this even if the local and remote hosts share a common filesystem,
because we cannot be sure if finding the expected suite registration
implies a common filesystem or a different remote suite that happens to
be registered under the same name. User accounts used for remote control
must therefore install the passphrase in the secondary standard
locations (below) or use the command line option to explicitly reveal
the location. Remote tasks with 'ssh messaging = True' look first in the 
suite definition directory of the suite host, which they know through 
the variable CYLC_SUITE_DEF_PATH_ON_SUITE_HOST in the task execution
environment.

3/ Secondary locations:
    (i) $HOME/.cylc/SUITE_HOST/SUITE_OWNER/SUITE_NAME/passphrase
   (ii) $HOME/.cylc/SUITE_HOST/SUITE_NAME/passphrase
  (iii) $HOME/.cylc/SUITE_NAME/passphrase
These are more sensible locations for remote suite control from accounts
that do not actually need the suite definition directory to be installed.
"""
        location = None

        # 1/ given location
        if pfile:
            if os.path.isdir( pfile ):
                # if a directory is given assume the filename
                pfile = os.path.join( pfile, 'passphrase' )
            if os.path.isfile( pfile ):
                location = pfile
            else:
                # if an explicit location is given, the file must exist
                raise SecurityError, 'ERROR: passphrase not found: ' + pfile

        # 2/ suite definition directory from the task execution environment
        if not location:
            try:
                # Test for presence of task execution environment
                suite_host = os.environ['CYLC_SUITE_HOST']
            except KeyError:
                # not called by a task
                pass
            else:
                # called by a task
                if not is_remote_host( suite_host ):
                    # On suite host, called by a task. Could be a local
                    # task or a remote task that has ssh-messaged back
                    # to the suite host, so determine the suite
                    # definition directory by
                    # $CYLC_SUITE_DEF_PATH_ON_SUITE_HOST (which never
                    # changes) not $CYLC_SUITE_DEF_PATH (which gets
                    # modified for remote tasks (for the remote dir).
                    try:
                        pfile = os.path.join( os.environ['CYLC_SUITE_DEF_PATH_ON_SUITE_HOST'], 'passphrase' )
                    except KeyError:
                        pass
                    else:
                        if os.path.isfile( pfile ):
                            location = pfile

        # 3/ suite definition directory from local registration
        if not location and suiterc:
            pfile = os.path.join( os.path.dirname(suiterc), 'passphrase' )
            if os.path.isfile( pfile ):
                location = pfile

        # 4/ other allow locations as documented
        if not location:
            locations = []
            locations.append( os.path.join( os.environ['HOME'], '.cylc', self.host, self.owner, self.suite, 'passphrase' ))
            locations.append( os.path.join( os.environ['HOME'], '.cylc', self.host, self.suite, 'passphrase' ))
            locations.append( os.path.join( os.environ['HOME'], '.cylc', self.suite, 'passphrase' ))
            for pfile in locations:
                if os.path.isfile( pfile ):
                    location = pfile
                    break

        if not location:
            raise SecurityError, 'ERROR: suite passphrase not found.'

        return location

    def generate( self, dir ):
        pfile = os.path.join(dir, 'passphrase')
        if os.path.isfile( pfile ):
            try:
                self.get( pfile )
                return
            except SecurityError:
                pass
        # Note: Perhaps a UUID might be better here?
        char_set = string.ascii_uppercase + string.ascii_lowercase + string.digits
        self.passphrase = ''.join(random.sample(char_set, 20))
        mkdir_p(dir)
        f = open(pfile, 'w')
        f.write(self.passphrase)
        f.close()
        # set passphrase file permissions to owner-only
        os.chmod( pfile, 0600 )

    def get( self, pfile=None, suiterc=None ):
        ppfile = self.get_passphrase_file( pfile, suiterc )
        psf = open( ppfile, 'r' )
        lines = psf.readlines()
        psf.close()
        if len(lines) == 0:
            raise InvalidPassphraseError, 'Passphrase file is empty: ' + ppfile
        if len(lines) > 1:
            raise InvalidPassphraseError, 'Passphrase file contains multiple lines: ' + ppfile
        # chomp trailing whitespace and newline
        self.passphrase = lines[0].strip()
        return self.passphrase

