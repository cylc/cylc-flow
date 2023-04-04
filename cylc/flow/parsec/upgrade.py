# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

import contextlib
from logging import DEBUG, WARNING

from cylc.flow import LOG
from cylc.flow.parsec.exceptions import UpgradeError
from cylc.flow.parsec.OrderedDict import OrderedDict


class converter:
    """Create custom config value converters."""

    def __init__(self, callback, descr):
        self.callback = callback
        self.descr = descr

    def describe(self):
        return self.descr

    def convert(self, val):
        return self.callback(val)


class upgrader:
    """Handles upgrading of deprecated config values."""

    SITE_CONFIG = 'site config'
    USER_CONFIG = 'user config'

    def __init__(self, cfg, descr):
        """Store the config dict to be upgraded if necessary."""
        self.cfg = cfg
        self.descr = descr
        # upgrades must be ordered in case several act on the same item
        self.upgrades = OrderedDict()

    def deprecate(
        self, vn, oldkeys, newkeys=None,
        cvtr=None, silent=False, is_section=False,
    ):
        """Replace a deprecated key from a config
        Args:
            vn (str):
                Version at which this deprecation occurs.
            oldkeys (list):
                Path within config to be changed.
            newkeys (list):
                New location in the config for the item in "oldkeys".
            cvtr (cylc.flow.parsec.upgrade.Converter):
                Converter object containing a conversion function and a
                description of that function.
            silent (bool):
                Set silent mode for this upgrade.
            is_section (bool):
                Is a section heading.
        """
        if vn not in self.upgrades:
            self.upgrades[vn] = []
        if cvtr is None:
            cvtr = converter(lambda x: x, "value unchanged")  # identity
        self.upgrades[vn].append(
            {
                'old': oldkeys, 'new': newkeys, 'cvt': cvtr,
                'silent': silent, 'is_section': is_section
            })

    def obsolete(self, vn, oldkeys, silent=False, is_section=False):
        """Remove an obsolete key from a config
        Args:
            vn (str):
                Version at which this obsoletion occurs.
            oldkeys (list):
                Path within config to be removed.
            silent:
                Set silent mode for this upgrade.
            is_section (bool):
                Is a section heading.
        """
        if vn not in self.upgrades:
            self.upgrades[vn] = []
        cvtr = converter(lambda x: x, "DELETED (OBSOLETE)")  # identity
        self.upgrades[vn].append(
            {
                'old': oldkeys, 'new': None, 'cvt': cvtr, 'silent': silent,
                'is_section': is_section
            })

    def get_item(self, keys):
        item = self.cfg
        for key in keys:
            try:
                item = item[key]
            except TypeError:
                raise UpgradeError(
                    f'{self.show_keys(keys[:-1], True)}'
                    f' ("{keys[-2]}" should be a [section] not a setting)'
                )
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
    def show_keys(keys, is_section):
        res = ""
        for key in keys:
            if key != keys[-1] or is_section:
                res += f"[{key}]"
            else:
                res += key
        return res

    def expand(self, upg):
        """Expands __MANY__ items."""
        if '__MANY__' not in upg['old']:
            return [upg]
        if upg['old'].count('__MANY__') > 1:
            raise UpgradeError(
                f"Multiple simultaneous __MANY__ not supported: {upg['old']}")
        exp_upgs = []
        pre = []
        post = []
        many = []
        okeys = upg['old']
        for i, k in enumerate(okeys):
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
                        'is_section': upg['is_section'],
                    })
                return exp_upgs
            npre = []
            npost = []
            for k in nkeys:
                i += 1  # noqa: SIM113 (multiple loops interacting)
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
                    'is_section': upg['is_section'],
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
                        msg = self.show_keys(upg['old'], upg['is_section'])
                        if upg['new']:
                            msg += ' -> ' + self.show_keys(upg['new'],
                                                           upg['is_section'])
                        msg += " - " + upg['cvt'].describe()
                        if not upg['silent']:
                            warnings.setdefault(vn, [])
                            warnings[vn].append(msg)
                        self.del_item(upg['old'])
                        if upg['new']:
                            # check self.cfg does not already contain a
                            # non-deprecated item matching upg['new']:
                            nval = ""
                            with contextlib.suppress(KeyError):
                                nval = self.get_item(upg['new'])
                            if nval:
                                # Conflicting item exists, with non-null value.
                                raise UpgradeError(
                                    'ERROR: Cannot upgrade deprecated '
                                    f'item "{msg}" because the upgraded '
                                    'item already exists'
                                )
                            self.put_item(upg['new'],
                                          upg['cvt'].convert(old))
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
            LOG.log(level,
                    'deprecated items were automatically upgraded in '
                    f'"{self.descr}"')
            for vn, msgs in warnings.items():
                for msg in msgs:
                    LOG.log(level, ' * (%s) %s', vn, msg)
