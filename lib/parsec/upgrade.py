#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Support automatic deprecation and obsoletion of parsec config items."""

from logging import DEBUG, WARNING

from parsec import LOG
from parsec.exceptions import UpgradeError
from parsec.OrderedDict import OrderedDict


class converter(object):
    """Create custom config value converters."""

    def __init__(self, callback, descr):
        self.callback = callback
        self.descr = descr

    def describe(self):
        return self.descr

    def convert(self, val):
        return self.callback(val)


class upgrader(object):
    """Handles upgrading of deprecated config values."""

    SITE_CONFIG = 'site config'
    USER_CONFIG = 'user config'

    def __init__(self, cfg, descr):
        """Store the config dict to be upgraded if necessary."""
        self.cfg = cfg
        self.descr = descr
        # upgrades must be ordered in case several act on the same item
        self.upgrades = OrderedDict()

    def deprecate(self, vn, oldkeys, newkeys=None, cvtr=None, silent=False):
        if vn not in self.upgrades:
            self.upgrades[vn] = []
        if cvtr is None:
            cvtr = converter(lambda x: x, "value unchanged")  # identity
        self.upgrades[vn].append(
            {'old': oldkeys, 'new': newkeys, 'cvt': cvtr, 'silent': silent})

    def obsolete(self, vn, oldkeys, newkeys=None, silent=False):
        if vn not in self.upgrades:
            self.upgrades[vn] = []
        cvtr = converter(lambda x: x, "DELETED (OBSOLETE)")  # identity
        self.upgrades[vn].append(
            {'old': oldkeys, 'new': newkeys, 'cvt': cvtr, 'silent': silent})

    def get_item(self, keys):
        item = self.cfg
        for key in keys:
            item = item[key]
        return item

    def put_item(self, keys, val):
        item = self.cfg
        for key in keys[:-1]:
            if key not in item:
                item[key] = {}
            item = item[key]
        item[keys[-1]] = val

    def del_item(self, keys):
        item = self.cfg
        for key in keys[:-1]:
            item = item[key]
        del item[keys[-1]]

    @staticmethod
    def show_keys(keys):
        return '[' + ']['.join(keys) + ']'

    def expand(self, upg):
        """Expands __MANY__ items."""
        if '__MANY__' not in upg['old']:
            return [upg]
        if upg['old'].count('__MANY__') > 1:
            raise UpgradeError(
                'Multiple simultaneous __MANY__ not supported: %s' %
                upg['old'])
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
                post = okeys[i + 1:]
                tmp = self.cfg
                for j in pre:
                    tmp = tmp[j]
                many = list(tmp.keys())
                break
        if not many:
            exp_upgs.append(upg)
        else:
            i = -1
            nkeys = upg['new']
            if nkeys is None:  # No new keys defined.
                for m in many:
                    exp_upgs.append({
                        'old': pre + [m] + post,
                        'new': None,
                        'cvt': upg['cvt'],
                        'silent': upg['silent'],
                    })
                return exp_upgs
            npre = []
            npost = []
            for k in nkeys:
                i += 1
                if k == "__MANY__":
                    npre = nkeys[:i]
                    npost = nkeys[i + 1:]
            if not npre or not npost:
                raise UpgradeError('__MANY__ mismatch')
            for m in many:
                exp_upgs.append({
                    'old': pre + [m] + post,
                    'new': npre + [m] + npost,
                    'cvt': upg['cvt'],
                    'silent': upg['silent'],
                })
        return exp_upgs

    def upgrade(self):
        warnings = OrderedDict()
        for vn, upgs in self.upgrades.items():
            for u in upgs:
                try:
                    exp = self.expand(u)
                except (KeyError, UpgradeError):
                    continue

                for upg in exp:
                    try:
                        old = self.get_item(upg['old'])
                    except KeyError:
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
                            warnings.setdefault(vn, [])
                            warnings[vn].append(msg)
                        self.del_item(upg['old'])
                        if upg['cvt'].describe() != "DELETED (OBSOLETE)":
                            self.put_item(upg['new'], upg['cvt'].convert(old))
        if warnings:
            level = WARNING
            if self.descr == self.SITE_CONFIG:
                # Site level configuration, user cannot easily fix.
                # Only log at debug level.
                level = DEBUG
            else:
                # User level configuration, user should be able to fix.
                # Log at warning level.
                level = WARNING
            LOG.log(
                level,
                "deprecated items were automatically upgraded in '%s':",
                self.descr)
            for vn, msgs in warnings.items():
                for msg in msgs:
                    LOG.log(level, ' * (%s) %s', vn, msg)


if __name__ == "__main__":
    import sys
    from parsec.util import printcfg

    cfg = {
        'item one': 1,
        'item two': 'move me up',
        'section A': {
            'abc': 5,
            'cde': 'foo',
        },
        'hostnames': {
            'host 1': {
                'work dir': '/a/b/c',
                'running dir': '/a/b/c/d'
            },
            'host 2': {
                'work dir': '/x/b/c',
                'running dir': '/x/b/c/d'
            },
        }
    }
    x2 = converter(lambda x: 2 * x, 'value x 2')

    printcfg(cfg)
    sys.stdout.write('\n')

    upg = upgrader(cfg, 'test file')
    # successive upgrades are incremental - at least until I think of a
    # good way to remember what items have already been translated...
    upg.deprecate('1.3', ['item one'], ['item ONE'], x2)
    upg.deprecate('1.3', ['section A'], ['Heading A'])
    # NOTE change to new item keys here!
    upg.deprecate('1.3', ['Heading A', 'cde'], ['Heading A', 'CDE'])
    upg.deprecate('1.4', ['Heading A', 'abc'], cvtr=x2, silent=True)
    upg.deprecate(
        '1.4.1', ['item two'], ['Heading A', 'item two'], silent=True)
    upg.deprecate('1.5', ['hostnames'], ['hosts'])
    upg.deprecate(
        '1.5',
        ['hosts', '__MANY__', 'running dir'], ['hosts', '__MANY__', 'run dir'])

    upg.upgrade()

    sys.stdout.write('\n')
    printcfg(cfg)
