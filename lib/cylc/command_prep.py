#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
from cylc.passphrase import passphrase
from cylc.registration import localdb
from cylc.suite_host import is_remote_host
from cylc.owner import is_remote_user
from cylc.compat import compat_pyro, compat_file

class prep( object ):
    def __init__( self, suite, options ):
        self.options = options
        self.suite = suite
        self.suiterc = None
        self.suitedir = None
        # dealias the suite name (an aliased name may be given for local suites)
        if not is_remote_host( options.host ) and not is_remote_user( options.owner ):
            self.db = localdb(file=options.db, verbose=options.verbose)
            self.db.load_from_file()
            try:
                self.suite = self.db.unalias( suite )
                self.suiterc = self.db.getrc( suite )
                self.suitedir = os.path.dirname( self.suiterc )
            except Exception, x:
                if options.debug:
                    raise
                raise SystemExit(x)

    def execute( self ):
        if not self.options.override:
            # cylc version re-invocation
            self.compat.execute()
        return self.get_suite()

class prep_pyro( prep ):
    def __init__( self, suite, options ):
        prep.__init__( self, suite, options )
        # get the suite passphrase
        try:
            self.pphrase = passphrase( self.suite, self.options.owner, self.options.host,
                    verbose=options.verbose ).get( self.options.pfile, self.suitedir )
        except Exception, x:
            if self.options.debug:
                raise
            raise SystemExit(x)
        self.compat = compat_pyro( self.suite, self.options.owner,
                self.options.host, self.options.port, self.pphrase,
                self.options.pyro_timeout, self.options.verbose,
                self.options.debug)

    def get_suite( self ):
        return self.suite, self.pphrase

class prep_file( prep ):
    def __init__( self, suite, options ):
        prep.__init__( self, suite, options )
        self.compat = compat_file( self.suite, self.suiterc,
                options.templatevars, options.templatevars_file,
                options.verbose, options.debug)

    def get_version( self ):
        return self.compat.get_version()

    def get_suite( self ):
        return self.suite, self.suiterc

    def get_rcfiles( self ):
        return self.db.get_rcfiles( self.suite )

