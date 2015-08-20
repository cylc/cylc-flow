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

import sys
if __name__ == '__main__':
    import os
    here = os.path.dirname( __file__ )
    sys.path.append( here + '/..' )

from parsec import ParsecError
from parsec.OrderedDict import OrderedDict
import cylc.flags

"""Support automatic deprecation and obsoletion of parsec config items."""

class UpgradeError(ParsecError):
    pass

class converter( object ):
    """Create custom config value converters."""
    def __init__( self, callback, descr ):
        self.callback = callback
        self.descr = descr
    def describe( self ):
        return self.descr
    def convert( self, val ):
        return self.callback( val)

class upgrader( object ):
    """Handles upgrading of deprecated config values."""

    def __init__( self, cfg, descr ):
        """Store the config dict to be upgraded if necessary."""
        self.cfg = cfg
        self.descr = descr
        # upgrades must be ordered in case several act on the same item
        self.upgrades = OrderedDict()

    def deprecate(self, vn, oldkeys, newkeys=None, cvtr=None, silent=False):
        if vn not in self.upgrades:
            self.upgrades[vn] = []
        if cvtr is None:
            cvtr = converter(lambda x: x, "value unchanged") # identity
        self.upgrades[vn].append(
            {
                'old': oldkeys,
                'new': newkeys,
                'cvt': cvtr,
                'silent': silent
            }
        )

    def obsolete(self, vn, oldkeys, newkeys=None, silent=False):
        if vn not in self.upgrades:
            self.upgrades[vn] = []
        cvtr = converter(lambda x: x, "DELETED (OBSOLETE)") # identity
        self.upgrades[vn].append(
            {
                'old' : oldkeys,
                'new' : newkeys,
                'cvt' : cvtr,
                'silent': silent 
            }
        )

    def get_item( self, keys ):
        item = self.cfg
        for key in keys:
            item = item[key]
        return item

    def put_item( self, keys, val ):
        item = self.cfg
        for key in keys[:-1]:
            if key not in item:
                item[key] = {}
            item = item[key]
        item[keys[-1]] = val

    def del_item( self, keys ):
        item = self.cfg
        for key in keys[:-1]:
            item = item[key]
        del item[keys[-1]]

    def show_keys( self, keys ):
        return '[' + ']['.join(keys) + ']'

    def expand( self, upg ):
        """Expands __MANY__ items."""
        if '__MANY__' not in upg['old']:
            return [upg]
        if upg['old'].count( '__MANY__' ) > 1:
            print >> sys.stderr, upg['old']
            raise UpgradeError("Multiple simultaneous __MANY__ not supported")
        exp_upgs = []
        pre = []
        post = []
        many = []
        i = -1
        okeys = upg['old']
        for k in okeys:
            i += 1
            if k == "__MANY__":
                pre = okeys[:i]
                post = okeys[i+1:]
                tmp = self.cfg
                for j in pre:
                    tmp = tmp[j]
                many = tmp.keys()
                break
        if not many:
            exp_upgs.append( upg )
        else:
            i = -1
            nkeys = upg['new']
            npre = []
            npost = []
            for k in nkeys:
                i += 1
                if k == "__MANY__":
                    npre = nkeys[:i]
                    npost = nkeys[i+1:]
            if not npre or not npost:
                raise UpgradeError('ERROR: __MANY__ mismatch')
            for m in many:
                exp_upgs.append( {
                    'old': pre + [m] + post,
                    'new': npre + [m] + npost,
                    'cvt': upg['cvt'],
                    'silent': upg['silent']
                    })
        return exp_upgs

    def upgrade( self ):
        warnings = OrderedDict()
        do_warn = False
        for vn, upgs in self.upgrades.items():
            warnings[vn] = []

            for u in upgs:
                try:
                    exp = self.expand(u)
                except:
                    continue

                for upg in exp:
                    try:
                        old = self.get_item( upg['old'] )
                    except:
                        # OK: deprecated item not found
                        pass
                    else:
                        msg = self.show_keys(upg['old'])
                        if upg['new']:
                            msg += ' -> ' + self.show_keys(upg['new'])
                        else:
                            upg['new'] = upg['old']
                        msg += " - " + upg['cvt'].describe()
                        if not upg['silent']:
                            warnings[vn].append( msg )
                            do_warn = True
                        self.del_item( upg['old'] )
                        if upg['cvt'].describe() != "DELETED (OBSOLETE)":
                            self.put_item( upg['new'], upg['cvt'].convert(old) )
        if do_warn and cylc.flags.verbose:
            print >> sys.stderr, "WARNING: deprecated items were automatically upgraded in '" + self.descr + "':"
            for vn,msgs in warnings.items():
                for m in msgs:
                    print >> sys.stderr, " * (" + vn + ")", m

if __name__ == "__main__":
    from util import printcfg
    cylc.flags.verbose = True

    cfg = {
            'item one' : 1,
            'item two' : 'move me up',
            'section A' :
            {
                'abc' : 5,
                'cde' : 'foo',
                },
            'hostnames' :
            {
                'host 1' :
                {
                    'work dir' : '/a/b/c',
                    'running dir' : '/a/b/c/d'
                    },
                'host 2' :
                {
                    'work dir' : '/x/b/c',
                    'running dir' : '/x/b/c/d'
                    },
                }
            }
    x2 = converter( lambda x: 2*x, 'value x 2' )

    printcfg(cfg)
    print

    upg = upgrader( cfg, 'test file' )
    # successive upgrades are incremental - at least until I think of a
    # good way to remember what items have already been translated...
    upg.deprecate( '1.3', ['item one' ], ['item ONE'], x2 )
    upg.deprecate( '1.3', ['section A'], ['Heading A'] )
    upg.deprecate( '1.3', ['Heading A','cde'], ['Heading A', 'CDE'] ) # NOTE change to new item keys here!
    upg.deprecate( '1.4', ['Heading A','abc'], cvtr=x2, silent=True )
    upg.deprecate( '1.4.1', ['item two'], ['Heading A','item two'], silent=True )
    upg.deprecate( '1.5', ['hostnames'], ['hosts'] )
    upg.deprecate( '1.5', ['hosts', '__MANY__', 'running dir'], ['hosts','__MANY__', 'run dir'] )

    upg.upgrade()

    print
    printcfg(cfg)
