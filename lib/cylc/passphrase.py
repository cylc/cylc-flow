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

    # dir can be passed in as the known suite def location, or via manual spec
    # on the command line.

    # The preferred passphrase file location is the suite definition
    # directory, because suite deployment systems such as Rose can
    # automatically install suites to remote task hosts.

    # Remote tasks can determine this location from their execution environments.

    # Note that we can only use the the registration database to determine the
    # suite definition directory location when $USER and $HOST are equal to the
    # suite owner and suite host. Otherwise finding the same registration name
    # could be a coincidence rather than indicating a shared filesystem.

    # Finally, for commands and GUI users can specify the passphrase location
    # manually on the command line, which results in exporting
    # $CYLC_SUITE_DEF_DIRECTORY as if in a task execution environment.
    print suite, dir, create

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
        print "A new random passphrase file has been generated for your suite:"
        print  location, """
It must be distributed to any local or remote task hosting user accounts, and to
any user account from which you intend to use cylc commands or GUIs to connect
to the running suite.  It may be held in either of the following locations...
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
