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

import Pyro.core
from copy import deepcopy
from datetime import datetime
import logging, os, sys
import cPickle as pickle
from cylc.broadcast_report import (
    get_broadcast_change_report, get_broadcast_bad_options_report)
from cylc.task_id import TaskID
from cycling.loader import get_point
from rundb import RecordBroadcastObject
from wallclock import get_current_time_string

class broadcast( Pyro.core.ObjBase ):
    """Receive broadcast variables from cylc clients."""

    # examples:
    #self.settings[ 'all-cycle-points' ][ 'root' ] = "{ 'environment' : { 'FOO' : 'bar' }}
    #self.settings[ '2010080806' ][ 'root' ] = "{ 'command scripting' : 'stuff' }

    def __init__(self, linearized_ancestors):
        self.log = logging.getLogger('main')
        self.settings = {}
        self.prev_dump = self.get_dump()
        self.settings_queue = []
        self.linearized_ancestors = linearized_ancestors
        Pyro.core.ObjBase.__init__(self)

    def prune(self):
        """Remove empty leaves left by unsetting broadcast values."""
        prunes = []
        stuffs = [([], self.settings, True)]
        while stuffs:
            keys, stuff, is_new = stuffs.pop()
            if is_new:
                stuffs.append((keys, stuff, False))
                for key, value in stuff.items():
                    if isinstance(value, dict):
                        stuffs.append((keys + [key], value, True))
            else:
                for key, value in stuff.items():
                    if not value:
                        del stuff[key]
                        prunes.append(keys + [key])
        return prunes

    def addict(self, target, source):
        """Recursively add source dict to target dict."""
        for key, val in source.items():
            if isinstance(val, dict):
                if key not in target:
                    target[key] = {}
                self.addict(target[key], val)
            else:
                if source[key]:
                    target[key] = source[key]
                elif key in target:
                    del target[key]

    def put(self, namespaces, point_strings, settings):
        """Add new broadcast settings."""
        modified_settings = []
        for setting in settings:
            for point_string in point_strings:
                if point_string not in self.settings:
                    self.settings[point_string] = {}
                for namespace in namespaces:
                    if namespace not in self.settings[point_string]:
                        self.settings[point_string][namespace] = {}
                    self.addict(
                        self.settings[point_string][namespace], setting)
                    modified_settings.append(
                        (point_string, namespace, setting))

        self.prune()
        self._update_db_queue()

        # Log the broadcast
        self.log.info(get_broadcast_change_report(modified_settings))

        return modified_settings

    def get(self, task_id=None):
        """Retrieve all broadcast variables that target a given task ID."""
        if not task_id:
            # all broadcast settings requested
            return self.settings
        name, point_string = TaskID.split(task_id)

        ret = {}
        # The order is:
        #    all:root -> all:FAM -> ... -> all:task
        # -> tag:root -> tag:FAM -> ... -> tag:task
        # DEPRECATED at cylc 6: 'all-cycles'
        for cycle in ['all-cycle-points', 'all-cycles', point_string]:
            if cycle not in self.settings:
                continue
            for ns in reversed(self.linearized_ancestors[name]):
                if ns in self.settings[cycle]:
                    self.addict(ret, self.settings[cycle][ns])
        return ret

    def expire(self, cutoff):
        """Clear all settings targetting cycle points earlier than cutoff."""
        if not cutoff:
            self.log.info('Expiring all broadcast settings now')
            self.settings = {}
        for point_string in self.settings.keys():
            # DEPRECATED at cylc 6: 'all-cycles'
            if point_string in ['all-cycle-points', 'all-cycles']:
                continue
            point = get_point(point_string)
            if point < cutoff:
                self.log.info('Expiring ' + str(point) + ' broadcast settings now')
                del self.settings[ point_string ]

    def clear(self, namespaces, point_strings, cancel_settings=None):
        """Clear settings globally, or for listed namespaces and/or points."""
        # If cancel_settings defined, only clear specific settings
        cancel_keys_list = []
        if cancel_settings:
            for cancel_setting in cancel_settings:
                stuffs = [([], cancel_setting)]
                while stuffs:
                    keys, stuff = stuffs.pop()
                    for key, value in stuff.items():
                        if isinstance(value, dict):
                            stuffs.append((keys + [key], value))
                        else:
                            cancel_keys_list.append(keys + [key])
        # Clear settings
        modified_settings = []
        for point_string, point_string_settings in self.settings.items():
            if point_strings and point_string not in point_strings:
                continue
            for namespace, namespace_settings in point_string_settings.items():
                if namespaces and namespace not in namespaces:
                    continue
                stuffs = [([], namespace_settings)]
                while stuffs:
                    keys, stuff = stuffs.pop()
                    for key, value in stuff.items():
                        if isinstance(value, dict):
                            stuffs.append((keys + [key], value))
                        elif (not cancel_keys_list or
                                keys + [key] in cancel_keys_list):
                            stuff[key] = None
                            setting = {key: value}
                            for rkey in reversed(keys):
                                setting = {rkey: setting}
                            modified_settings.append(
                                (point_string, namespace, setting))

        # Prune any empty branches
        bad_options = self._get_bad_options(
            self.prune(), point_strings, namespaces, cancel_keys_list)
        self._update_db_queue()

        # Log the broadcast
        self.log.info(
            get_broadcast_change_report(modified_settings, is_cancel=True))
        if bad_options:
            self.log.error(get_broadcast_bad_options_report(bad_options))

        return (modified_settings, bad_options)

    def dump(self, file_):
        """Write broadcast variables to the state dump file."""
        pickle.dump(self.settings, file_)
        file_.write("\n")

    def get_db_ops(self):
        """Return the next DB operations from DB queue."""
        ops = self.settings_queue
        self.settings_queue = []
        return ops

    def get_dump(self):
        """Return broadcast variables as written to the state dump file."""
        return pickle.dumps(self.settings) + "\n"

    def load(self, pickled_settings):
        """Load broadcast variables from the state dump file."""
        self.settings = pickle.loads(pickled_settings)

    @staticmethod
    def _get_bad_options(prunes, point_strings, namespaces, cancel_keys_list):
        """Return unpruned namespaces and/or point_strings options."""
        bad_options = {
            "point_strings": None, "namespaces": None, "cancel": None}
        if point_strings:
            bad_options["point_strings"] = set(point_strings)
            for point_string in point_strings:
                if point_string in [prune[0] for prune in prunes]:
                    bad_options["point_strings"].discard(point_string)
                    if not bad_options["point_strings"]:
                        break
        if namespaces:
            bad_options["namespaces"] = set(namespaces)
            for namespace in namespaces:
                if namespace in [prune[1] for prune in prunes if prune[1:]]:
                    bad_options["namespaces"].discard(namespace)
                    if not bad_options["namespaces"]:
                        break
        if cancel_keys_list:
            bad_options["cancel"] = set(
                [tuple(cancel_keys) for cancel_keys in cancel_keys_list])
            for cancel_keys in cancel_keys_list:
                if (list(cancel_keys) in
                        [prune[2:] for prune in prunes if prune[2:]]):
                    bad_options["cancel"].discard(tuple(cancel_keys))
                    if not bad_options["cancel"]:
                        break
        for key, value in bad_options.items():
            if value:
                bad_options[key] = list(value)
            else:
                del bad_options[key]
        return bad_options

    def _update_db_queue(self):
        """Update the queue to the runtime DB."""
        this_dump = self.get_dump()
        if this_dump != self.prev_dump:
            now = get_current_time_string(display_sub_seconds=True)
            self.settings_queue.append(RecordBroadcastObject(now, this_dump))
            self.prev_dump = this_dump
