#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

class passphrase:
    def __init__( self, suite ):

        file = os.path.join( os.environ['HOME'], '.cylc', 'security', suite )

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
