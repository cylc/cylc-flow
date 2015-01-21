#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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
from suite_host import get_hostname, is_remote_host
from owner import user, is_remote_user
import flags

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
    def __init__( self, suite, owner=user, host=get_hostname() ):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.location = None

        ### ?? this doesn't matter, we now set permissions explicitly:
        ### ?? TODO - handle existing file that owner can't read? etc.?
        ##mode = os.stat( ppfile )[ST_MODE]
        ##if not S_IRUSR & mode:
        ##    raise PassphraseNotReadableError, 'Owner cannot read passphrase file: ' + ppfile
        ##if S_IROTH & mode or S_IWOTH & mode or S_IXOTH & mode:
        ##    raise InsecurePassphraseError, 'OTHERS have access to passphrase file: ' + ppfile
        ##if S_IRGRP & mode or S_IWGRP & mode or S_IXGRP & mode:
        ##    raise InsecurePassphraseError, 'GROUP has access to passphrase file: ' + ppfile

    def get_passphrase_file( self, pfile=None, suitedir=None ):
        """
Passphrase location, order of preference:

1/ The pfile argument - used for passphrase creation by "cylc register".

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
        # 1/ explicit location given on the command line
        if pfile:
            if os.path.isdir( pfile ):
                # if a directory is given assume the filename
                pfile = os.path.join( pfile, 'passphrase' )
            if os.path.isfile( pfile ):
                self.set_location( pfile )

            else:
                # if an explicit location is given, the file must exist
                raise SecurityError, 'ERROR, file not found on ' + user + '@' + get_hostname() + ': ' + pfile

        # 2/ cylc commands with suite definition directory from local registration
        if not self.location and suitedir:
            pfile = os.path.join( suitedir, 'passphrase' )
            if os.path.isfile( pfile ):
                self.set_location( pfile )

        # (2 before 3 else sub-suites load their parent suite's
        # passphrase on start-up because the "cylc run" command runs in
        # a parent suite task execution environment).

        # 3/ running tasks: suite definition directory (from the task execution environment)
        if not self.location:
            try:
                # Test for presence of task execution environment
                suite_host = os.environ['CYLC_SUITE_HOST']
                suite_owner = os.environ['CYLC_SUITE_OWNER']
            except KeyError:
                # not called by a task
                pass
            else:
                # called by a task
                if is_remote_host( suite_host ) or is_remote_user( suite_owner ):
                    # 2(i)/ cylc messaging calls on a remote account.

                    # First look in the remote suite definition
                    # directory ($CYLC_SUITE_DEF_PATH is modified for
                    # remote tasks):
                    try:
                        pfile = os.path.join( os.environ['CYLC_SUITE_DEF_PATH'], 'passphrase' )
                    except KeyError:
                        pass
                    else:
                        if os.path.isfile( pfile ):
                            self.set_location( pfile )

                else:
                    # 2(ii)/ cylc messaging calls on the suite host and account.

                    # Could be a local task or a remote task with 'ssh
                    # messaging = True'. In either case use
                    # $CYLC_SUITE_DEF_PATH_ON_SUITE_HOST which never
                    # changes, not $CYLC_SUITE_DEF_PATH which gets
                    # modified for remote tasks as described above.
                    try:
                        pfile = os.path.join( os.environ['CYLC_SUITE_DEF_PATH_ON_SUITE_HOST'], 'passphrase' )
                    except KeyError:
                        pass
                    else:
                        if os.path.isfile( pfile ):
                            self.set_location( pfile )

        # 4/ other allowed locations, as documented above
        if not self.location:
            locations = []
            # For remote control commands, self.host here will be fully
            # qualified or not depending on what's given on the command line.
            short_host = re.sub( '\..*', '', self.host )

            locations.append( os.path.join( os.environ['HOME'], '.cylc', self.host, self.owner, self.suite, 'passphrase' ))
            if short_host != self.host:
                locations.append( os.path.join( os.environ['HOME'], '.cylc', short_host, self.owner, self.suite, 'passphrase' ))
            locations.append( os.path.join( os.environ['HOME'], '.cylc', self.host, self.suite, 'passphrase' ))
            if short_host != self.host:
                locations.append( os.path.join( os.environ['HOME'], '.cylc', short_host, self.suite, 'passphrase' ))
            locations.append( os.path.join( os.environ['HOME'], '.cylc', self.suite, 'passphrase' ))
            for pfile in locations:
                if os.path.isfile( pfile ):
                    self.set_location( pfile )
                    break

        if not self.location:
            raise SecurityError, 'ERROR: passphrase for suite ' + self.suite + ' not found on ' + user + '@' + get_hostname()

        return self.location

    def set_location( self, pfile ):
        if flags.verbose:
            print 'Passphrase detected at', pfile, 'on', user + '@' + get_hostname()
        self.location = pfile

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
        if flags.verbose:
            print 'Generated suite passphrase file on', user + '@' + get_hostname() + ':', pfile

    def get( self, pfile=None, suitedir=None ):
        ppfile = self.get_passphrase_file( pfile, suitedir )
        psf = open( ppfile, 'r' )
        lines = psf.readlines()
        psf.close()
        if len(lines) == 0:
            raise InvalidPassphraseError, 'ERROR, passphrase file is empty, on ' + user + '@' + get_hostname() + ': ' + ppfile
        if len(lines) > 1:
            raise InvalidPassphraseError, 'ERROR, passphrase file contains multiple lines, on ' + user + '@' + get_hostname() + ': ' + ppfile
        # chomp trailing whitespace and newline
        self.passphrase = lines[0].strip()
        return self.passphrase
