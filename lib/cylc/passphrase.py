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

def get_filename( suite, dir=None, create=False ):
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

3/ $HOME/.cylc/SUITE/; this is a more sensible location for enabling
remote suite control from accounts that do not actually need the suite
definition directory to be installed.

So... if locations 1 and/or 2 are known, they will be checked first. If
not known, or if a passphrase is not found there, the secondary location
will be checked.
    """
# TO DO: IMPLEMENT THE ABOVE LOCATION LOGIC BELOW!
    preferred = None 
    location = None
    if dir:
        if not dir.endswith('passphrase'):
            preferred = os.path.join( dir, 'passphrase' )
        else:
            preferred = dir
    else:
        try:
            preferred = os.path.join( os.environ['CYLC_SUITE_DEF_PATH'], 'passphrase' )
        except KeyError:
            pass

    if preferred:
        if os.path.isfile( preferred ) or create:
            location = preferred
    if not location:
        location = os.path.join( os.environ['HOME'], '.cylc', suite, 'passphrase' )

    if not os.path.isfile( location ) and create:
        char_set = string.ascii_uppercase + string.ascii_lowercase + string.digits
        pphrase = ''.join(random.sample(char_set,20))
        mkdir_p( os.path.dirname( location ))
        f = open(location, 'w')
        f.write(pphrase)
        f.close()
        print """
________________________________________________________________________
A new random passphrase has been generated for this suite:\n   """, location, """
It must be distributed to any other user accounts (local or remote)
that host this suite's tasks, and similarly to any user accounts from
which cylc commands will be used to connect to the running suite. 

Cylc's remote task messaging commands will look for the passphrase at 
$CYLC_SUITE_DEF_PATH/passphrase; if not found there (e.g. if the suite
definition is not installed on a remote task host) they will look in
$HOME/.cylc/SUITE/passphrase. You may also use the latter location 
for remote suite control (in which case the suite definition directory
will not be known) or you can specify the location on the commandline.
------------------------------------------------------------------------
"""
        # set passphrase file permissions to owner-only
        os.chmod( location, 0600 )

    return location

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
    def __init__( self, suite, pfile=None ):

        file = get_filename( suite, pfile )

        if not os.path.isfile( file ):
            raise PassphraseNotFoundError, 'File not found: ' + file

        mode = os.stat( file )[ST_MODE]

        if not S_IRUSR & mode:
            raise PassphraseNotReadableError, 'Owner cannot read passphrase file: ' + file

        if S_IROTH & mode or S_IWOTH & mode or S_IXOTH & mode:
            raise InsecurePassphraseError, 'OTHERS have access to passphrase file: ' + file

        if S_IRGRP & mode or S_IWGRP & mode or S_IXGRP & mode:
            raise InsecurePassphraseError, 'GROUP has access to passphrase file: ' + file

        psf = open( file, 'r' )
        lines = psf.readlines()
        if len(lines) != 1:
            raise InvalidPassphraseError, 'Passphrase file contains multiple lines: ' + file

        line0 = lines[0]
        # chomp trailing whitespace and newline
        self.passphrase = re.sub( '\s*\n', '', line0 )

    def get( self ):
        return self.passphrase
