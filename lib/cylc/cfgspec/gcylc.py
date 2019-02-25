#!/usr/bin/env python2

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
"gcylc config file format."

import os
import sys
from copy import deepcopy, copy

from parsec import ParsecError
from parsec.config import ParsecConfig, ItemNotFoundError, itemstr
from parsec.upgrade import upgrader
from parsec.util import printcfg
from cylc import LOG
from cylc.cfgvalidate import (
    cylc_config_validate, CylcConfigValidator as VDR, DurationFloat)
from cylc.task_state import (
    TASK_STATUSES_ALL, TASK_STATUS_RUNAHEAD, TASK_STATUS_HELD,
    TASK_STATUS_WAITING, TASK_STATUS_EXPIRED, TASK_STATUS_QUEUED,
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED, TASK_STATUS_RETRYING)


OLD_SITE_FILE = os.path.join(
    os.environ['CYLC_DIR'], 'etc', 'gcylcrc', 'themes.rc')
SITE_FILE = os.path.join(
    os.environ['CYLC_DIR'], 'etc', 'gcylc-themes.rc')
USER_FILE = os.path.join(os.environ['HOME'], '.cylc', 'gcylc.rc')
HEADINGS = (
    None, 'task', 'state', 'host', 'job system', 'job ID', 'T-submit',
    'T-start', 'T-finish', 'dT-mean', 'latest message',)

# Nested dict of spec items.
# Spec value is [value_type, default, allowed_2, allowed_3, ...]
# where:
# - value_type: value type (compulsory).
# - default: the default value (optional).
# - allowed_2, ...: the only other allowed values of this setting (optional).
SPEC = {
    'dot icon size': [
        VDR.V_STRING, "medium", "small", "medium", "large", "extra large"],
    'initial side-by-side views': [VDR.V_BOOLEAN],
    'initial views': [VDR.V_STRING_LIST, ["text"]],
    'maximum update interval': [VDR.V_INTERVAL, DurationFloat(15)],
    'sort by definition order': [VDR.V_BOOLEAN, True],
    'sort column': [VDR.V_STRING] + list(HEADINGS),
    'sort column ascending': [VDR.V_BOOLEAN, True],
    'sub-graphs on': [VDR.V_BOOLEAN, False],
    'task filter highlight color': [VDR.V_STRING, 'PowderBlue'],
    'task states to filter out': [
        VDR.V_STRING_LIST, [TASK_STATUS_RUNAHEAD]],
    'themes': {
        '__MANY__': {
            'inherit': [VDR.V_STRING, "default"],
            'defaults': [VDR.V_STRING_LIST],
            TASK_STATUS_WAITING: [VDR.V_STRING_LIST],
            TASK_STATUS_HELD: [VDR.V_STRING_LIST],
            TASK_STATUS_QUEUED: [VDR.V_STRING_LIST],
            TASK_STATUS_READY: [VDR.V_STRING_LIST],
            TASK_STATUS_EXPIRED: [VDR.V_STRING_LIST],
            TASK_STATUS_SUBMITTED: [VDR.V_STRING_LIST],
            TASK_STATUS_SUBMIT_FAILED: [VDR.V_STRING_LIST],
            TASK_STATUS_RUNNING: [VDR.V_STRING_LIST],
            TASK_STATUS_SUCCEEDED: [VDR.V_STRING_LIST],
            TASK_STATUS_FAILED: [VDR.V_STRING_LIST],
            TASK_STATUS_RETRYING: [VDR.V_STRING_LIST],
            TASK_STATUS_SUBMIT_RETRYING: [VDR.V_STRING_LIST],
            TASK_STATUS_RUNAHEAD: [VDR.V_STRING_LIST],
        },
    },
    'transpose dot': [VDR.V_BOOLEAN],
    'transpose graph': [VDR.V_BOOLEAN],
    'ungrouped views': [VDR.V_STRING_LIST],
    'use theme': [VDR.V_STRING, "default"],
    'window size': [VDR.V_INTEGER_LIST, [800, 500]],
}


def upg(cfg, descr):
    u = upgrader(cfg, descr)
    u.deprecate(
        '5.4.3',
        ['themes', '__MANY__', 'submitting'],
        ['themes', '__MANY__', 'ready'])
    u.upgrade()


class GcylcConfig(ParsecConfig):
    """gcylc user configuration - default view panels, task themes etc."""

    _INST = None

    @classmethod
    def get_inst(cls):
        """Return default instance."""
        if cls._INST is None:
            cls._INST = cls(SPEC, upg)
            try:
                cls._INST.loadcfg(SITE_FILE, upgrader.SITE_CONFIG)
            except ParsecError as exc:
                LOG.warning(
                    'ignoring bad %s %s\n%s',
                    upgrader.SITE_CONFIG, SITE_FILE, exc)

            if os.access(USER_FILE, os.F_OK | os.R_OK):
                try:
                    cls._INST.loadcfg(USER_FILE, upgrader.USER_CONFIG)
                except ParsecError as exc:
                    LOG.error('bad %s %s', upgrader.USER_CONFIG, USER_FILE)
                    raise

            # check and correct initial view config etc.
            cls._INST.check()
            # add spec defaults and do theme inheritance
            cls._INST.transform()
        return cls._INST

    def __init__(self, spec, upg):
        ParsecConfig.__init__(self, spec, upg, validator=cylc_config_validate)
        self.default_theme = None
        self.use_theme = None

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
            sys.stderr.write("WARNING: theme %s not found, using '%s'\n" % (
                self.use_theme, self.default_theme))
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
                        sys.stderr.write(
                            "WARNING: undefined parent '%s' (theme '%s')\n" %
                            (parent, label))
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
                    sys.stderr.write(
                        ("WARNING, "
                         "ignoring illegal task state '%s' in theme %s\n") %
                        (state, theme))
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
                sys.stderr.write(
                    "WARNING: window size requires two values (x, y). "
                    "Using default.\n")
                fail = True
            elif cfg['window size'][0] < 0 or cfg['window size'][1] < 0:
                sys.stderr.write(
                    "WARNING: window size values must be positive. "
                    "Using default.\n")
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
                sys.stderr.write(
                    "WARNING: ignoring illegal view name '%s'\n" % (view))
                cfg['initial views'].remove(view)
        views = cfg['initial views']
        if len(views) == 0:
            # at least one view required
            sys.stderr.write(
                "WARNING: no initial views defined, defaulting to 'text'\n")
            cfg['initial views'] = ['text']

    @staticmethod
    def parse_state(theme, name, cfglist):
        allowed_keys = ['style', 'color', 'fontcolor']
        cfg = {}
        for item in cfglist:
            key, val = item.split('=')
            if key not in allowed_keys:
                sys.exit(
                    'ERROR, gcylc.rc, illegal: %s: %s = %s' %
                    (theme, name, cfglist))
            if key == 'color' or key == 'fontcolor':
                try:
                    import gtk
                    gtk.gdk.color_parse(val)
                except ValueError as exc:
                    sys.exit(
                        'ERROR, gcylc.rc, illegal color: %s: %s="%s"\n%s' %
                        (theme, name, item, exc))
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

    def dump(self, keys=None, sparse=False, pnative=False, prefix='',
             none_str=''):
        """Override parse.config.dump().

        To restore the list-nature of theme state items.
        """
        cfg = deepcopy(self.get([], sparse))
        try:
            for theme in cfg['themes'].values():
                for state in theme:
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
            print(cfg)
        else:
            printcfg(cfg, prefix=prefix, level=len(keys))
