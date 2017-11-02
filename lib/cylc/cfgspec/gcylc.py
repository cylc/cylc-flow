#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"gcylc config file format."

import os
import sys
import gtk
from copy import deepcopy, copy

from parsec import ParsecError
from parsec.config import config, ItemNotFoundError, itemstr
from parsec.validate import coercers, validator as vdr
from parsec.upgrade import upgrader
from parsec.util import printcfg
from cylc.gui.view_tree import ControlTree
from cylc.task_state import (
    TASK_STATUSES_ALL, TASK_STATUS_RUNAHEAD, TASK_STATUS_HELD,
    TASK_STATUS_WAITING, TASK_STATUS_EXPIRED, TASK_STATUS_QUEUED,
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED, TASK_STATUS_RETRYING)
from cylc.cfgspec.utils import (coerce_interval, DurationFloat)


coercers['interval'] = coerce_interval
SITE_FILE = os.path.join(
    os.environ['CYLC_DIR'], 'conf', 'gcylcrc', 'themes.rc')
USER_FILE = os.path.join(os.environ['HOME'], '.cylc', 'gcylc.rc')
SPEC = {
    'dot icon size': vdr(
        vtype='string',
        default="medium",
        options=["small", "medium", "large", "extra large"]),
    'initial side-by-side views': vdr(vtype='boolean', default=False),
    'initial views': vdr(vtype='string_list', default=["text"]),
    'maximum update interval': vdr(
        vtype='interval', default=DurationFloat(15)),
    'sort by definition order': vdr(vtype='boolean', default=True),
    'sort column': vdr(
        vtype='string',
        default='none',
        options=[heading for heading in ControlTree.headings if heading is not
                 None] + ['none']),
    'sort column ascending': vdr(vtype='boolean', default=True),
    'task filter highlight color': vdr(vtype='string', default='PowderBlue'),
    'task states to filter out': vdr(
        vtype='string_list',
        default=[TASK_STATUS_RUNAHEAD]),
    'themes': {
        '__MANY__': {
            'inherit': vdr(vtype='string', default="default"),
            'defaults': vdr(vtype='string_list'),
            TASK_STATUS_WAITING: vdr(vtype='string_list'),
            TASK_STATUS_HELD: vdr(vtype='string_list'),
            TASK_STATUS_QUEUED: vdr(vtype='string_list'),
            TASK_STATUS_READY: vdr(vtype='string_list'),
            TASK_STATUS_EXPIRED: vdr(vtype='string_list'),
            TASK_STATUS_SUBMITTED: vdr(vtype='string_list'),
            TASK_STATUS_SUBMIT_FAILED: vdr(vtype='string_list'),
            TASK_STATUS_RUNNING: vdr(vtype='string_list'),
            TASK_STATUS_SUCCEEDED: vdr(vtype='string_list'),
            TASK_STATUS_FAILED: vdr(vtype='string_list'),
            TASK_STATUS_RETRYING: vdr(vtype='string_list'),
            TASK_STATUS_SUBMIT_RETRYING: vdr(vtype='string_list'),
            TASK_STATUS_RUNAHEAD: vdr(vtype='string_list'),
        },
    },
    'transpose dot': vdr(vtype='boolean', default=False),
    'transpose graph': vdr(vtype='boolean', default=False),
    'ungrouped views': vdr(vtype='string_list', default=[]),
    'use theme': vdr(vtype='string', default="default"),
    'window size': vdr(vtype='integer_list', default=[800, 500]),
}


def upg(cfg, descr):
    u = upgrader(cfg, descr)
    u.deprecate(
        '5.4.3',
        ['themes', '__MANY__', 'submitting'],
        ['themes', '__MANY__', 'ready'])
    u.upgrade()


class gconfig(config):
    """gcylc user configuration - default view panels, task themes etc."""

    def transform(self):
        """
        1) theme inheritance
        2) turn state attribute lists into dicts for easier access:
          running : color=#ff00ff, style=filled, fontcolor=black
          becomes:
             running : { color:#ff00ff, style:filled, fontcolor:black }
        """
        # Note this is only done for the dense config structure.

        self.expand()
        self.default_theme = "default"

        cfg = self.get()

        # select the start-up theme
        self.use_theme = cfg['use theme']

        # and check it is valid
        if self.use_theme not in cfg['themes']:
            print >> sys.stderr, (
                "WARNING: theme " + self.use_theme + " not found, using '" +
                self.default_theme + "'")
            cfg['use theme'] = 'default'
            self.use_theme = self.default_theme

        # theme inheritance
        inherited = []
        for label in cfg['themes']:
            hierarchy = []
            name = label
            while True:
                hierarchy.append(name)
                if name == "default":
                    break
                if cfg['themes'][name]['inherit']:
                    parent = cfg['themes'][name]['inherit']
                    if parent not in cfg['themes']:
                        print >> sys.stderr, (
                            "WARNING: undefined parent '" + parent +
                            "' (theme '" + label + "')")
                        parent = "default"
                else:
                    break
                name = parent
            hierarchy.reverse()
            prev = hierarchy[0]
            theme = deepcopy(cfg['themes'][prev])
            for item in hierarchy[1:]:
                if item in inherited:
                    prev = item
                    continue
                # print 'Inherit:', item, '<--', prev
                self.inherit(theme, cfg['themes'][item])
                inherited.append(item)
            cfg['themes'][label] = theme

        # expand theme data
        cfg_themes = {}
        for theme in cfg['themes']:
            for key, val in cfg['themes'][self.default_theme].items():
                if not cfg['themes'][theme][key]:
                    cfg['themes'][theme][key] = val

            cfg_themes[theme] = {}
            defs = self.parse_state(
                theme, 'defaults', cfg['themes'][theme]['defaults'])

            for item, val in cfg['themes'][theme].items():
                if item in ['inherit', 'defaults']:
                    continue
                state = item
                if state not in TASK_STATUSES_ALL:
                    print >> sys.stderr, (
                        "WARNING, ignoring illegal task state '" + state +
                        "' in theme", theme)
                # reverse inherit (override)
                tcfg = deepcopy(defs)
                self.inherit(tcfg, self.parse_state(theme, item, val))
                cfg_themes[theme][state] = tcfg

        # final themes result:
        cfg['themes'] = cfg_themes

    def check(self):
        cfg = self.get(sparse=True)

        # check window size config
        if 'window size' in cfg:
            fail = False
            if len(cfg['window size']) != 2:
                print >> sys.stderr, ("WARNING: window size requires two "
                                      "values (x, y). Using default.")
                fail = True
            elif cfg['window size'][0] < 0 or cfg['window size'][1] < 0:
                print >> sys.stderr, ("WARNING: window size values must be "
                                      "positive. Using default.")
                fail = True
            # TODO: check for daft window sizes? (10, 5), (80000, 5000) ?
            if fail:
                cfg['window size'] = [800, 500]

        # check initial view config
        if 'initial views' not in cfg:
            return
        views = copy(cfg['initial views'])
        for view in views:
            if view not in ['dot', 'text', 'graph']:
                print >> sys.stderr, (
                    "WARNING: ignoring illegal view name '" + view + "'")
                cfg['initial views'].remove(view)
        views = cfg['initial views']
        if len(views) == 0:
            # at least one view required
            print >> sys.stderr, (
                "WARNING: no initial views defined, defaulting to 'text'")
            cfg['initial views'] = ['text']

    def parse_state(self, theme, name, cfglist=[]):
        allowed_keys = ['style', 'color', 'fontcolor']
        cfg = {}
        for item in cfglist:
            key, val = item.split('=')
            if key not in allowed_keys:
                raise SystemExit('ERROR, gcylc.rc, illegal: ' + theme + ': ' +
                                 name + ' = ' + cfglist)
            if key == 'color' or key == 'fontcolor':
                try:
                    gtk.gdk.color_parse(val)
                except ValueError as exc:
                    print >> sys.stderr, 'ERROR', exc
                    sys.exit('ERROR, gcylc.rc, illegal color: ' + theme +
                             ': ' + name + '="' + item + '"')
            cfg[key] = val
        return cfg

    def inherit(self, target, source):
        for item in source:
            if isinstance(source[item], dict):
                if item not in target:
                    target[item] = {}
                self.inherit(target[item], source[item])
            else:
                target[item] = source[item]

    def dump(self, keys=[], sparse=False, pnative=False, prefix='',
             none_str=''):
        # override parse.config.dump() to restore the list-nature of
        # theme state items
        cfg = deepcopy(self.get([], sparse))
        try:
            for theme in cfg['themes'].values():
                for state in theme.keys():
                    clist = []
                    for attr, val in theme[state].items():
                        clist.append('%s=%s' % (attr, val))
                    theme[state] = clist
        except (KeyError, AttributeError):
            pass

        parents = []
        for key in keys:
            try:
                cfg = cfg[key]
            except KeyError:
                raise ItemNotFoundError(itemstr(parents, key))
            else:
                parents.append(key)

        if pnative:
            print cfg
        else:
            printcfg(cfg, prefix=prefix, level=len(keys))


# load on import if not already loaded
gcfg = None
if not gcfg:
    gcfg = gconfig(SPEC, upg)
    try:
        gcfg.loadcfg(SITE_FILE, "site config")
    except ParsecError as exc:
        sys.stderr.write(
            "WARNING: ignoring bad site GUI config %s:\n"
            "%s\n" % (SITE_FILE, str(exc)))

    if os.access(USER_FILE, os.F_OK | os.R_OK):
        try:
            gcfg.loadcfg(USER_FILE, "user config")
        except ParsecError as exc:
            sys.stderr.write("ERROR: bad user GUI config %s:\n" % USER_FILE)
            raise

    # check and correct initial view config etc.
    gcfg.check()
    # add spec defaults and do theme inheritance
    gcfg.transform()
