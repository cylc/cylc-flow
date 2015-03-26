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
"""Handle broadcast from clients."""

import Pyro.core
import logging
import cPickle as pickle
from cylc.broadcast_report import (
    get_broadcast_change_report, get_broadcast_bad_options_report)
from cylc.task_id import TaskID
from cylc.cycling.loader import get_point
from cylc.rundb import RecordBroadcastObject
from cylc.wallclock import get_current_time_string


class Broadcast(Pyro.core.ObjBase):
    """Receive broadcast variables from cylc clients.

    Examples:
    self.settings['*']['root'] = {'environment': {'FOO': 'bar'}}
    self.settings['20100808T06Z']['root'] = {'command scripting': 'stuff'}
    """

    ALL_CYCLE_POINTS_STRS = ["*", "all-cycle-points", "all-cycles"]

    def __init__(self, linearized_ancestors):
        self.log = logging.getLogger('main')
        self.settings = {}
        self.prev_dump = self._get_dump()
        self.settings_queue = []
        self.linearized_ancestors = linearized_ancestors
        Pyro.core.ObjBase.__init__(self)

    def _prune(self):
        """Remove empty leaves left by unsetting broadcast values.

        Return a list of pruned settings in the form:

        [
            ["20200202", "foo", "command scripting"],
            ["20020202", "bar", "environment", "BAR"],
        ]
        """
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

    def _addict(self, target, source):
        """Recursively add source dict to target dict."""
        for key, val in source.items():
            if isinstance(val, dict):
                if key not in target:
                    target[key] = {}
                self._addict(target[key], val)
            else:
                if source[key]:
                    target[key] = source[key]
                elif key in target:
                    del target[key]

    def put(self, point_strings, namespaces, settings):
        """Add new broadcast settings.

        Return a list of modified settings in the form:
        [("20200202", "foo", {"command scripting": "true"}, ...]

        """
        modified_settings = []
        for setting in settings:
            for point_string in point_strings:
                if point_string not in self.settings:
                    self.settings[point_string] = {}
                for namespace in namespaces:
                    if namespace not in self.settings[point_string]:
                        self.settings[point_string][namespace] = {}
                    self._addict(
                        self.settings[point_string][namespace], setting)
                    modified_settings.append(
                        (point_string, namespace, setting))

        # Remove empty leaves
        self._prune()

        # Log the broadcast
        self._update_db_queue()
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
        for cycle in self.ALL_CYCLE_POINTS_STRS + [point_string]:
            if cycle not in self.settings:
                continue
            for namespace in reversed(self.linearized_ancestors[name]):
                if namespace in self.settings[cycle]:
                    self._addict(ret, self.settings[cycle][namespace])
        return ret

    def expire(self, cutoff):
        """Clear all settings targeting cycle points earlier than cutoff."""
        point_strings = []
        cutoff_point = None
        if cutoff is not None:
            cutoff_point = get_point(str(cutoff))
        for point_string in self.settings:
            if cutoff_point is None or (
                    point_string not in self.ALL_CYCLE_POINTS_STRS and
                    get_point(point_string) < cutoff_point):
                point_strings.append(point_string)
        if not point_strings:
            return (None, {"expire": [cutoff]})
        return self.clear(point_strings=point_strings)

    def clear(self, point_strings=None, namespaces=None, cancel_settings=None):
        """Clear settings globally, or for listed namespaces and/or points.

        Return a tuple (modified_settings, bad_options), where:
        * modified_settings is similar to the return value of the "put" method,
          but for removed settings.
        * bad_options is a dict in the form:
              {"point_strings": ["20020202", ..."], ...}
          The dict is only populated if there are options not associated with
          previous broadcasts. The keys can be:
          * point_strings: a list of bad point strings.
          * namespaces: a list of bad namespaces.
          * cancel: a list of tuples. Each tuple contains the keys of a bad
            setting.
        """
        # If cancel_settings defined, only clear specific settings
        cancel_keys_list = self._settings_to_keys_list(cancel_settings)

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
            self._prune(), point_strings, namespaces, cancel_keys_list)

        # Log the broadcast
        self._update_db_queue()
        self.log.info(
            get_broadcast_change_report(modified_settings, is_cancel=True))
        if bad_options:
            self.log.error(get_broadcast_bad_options_report(bad_options))

        return (modified_settings, bad_options)

    @staticmethod
    def _settings_to_keys_list(settings):
        """Return a list containing each setting dict keys as a list.

        E.g. Each setting in settings may look like:
        {"foo": {"bar": {"baz": 1}}}

        An element of the returned list will look like:
        ["foo", "bar", "baz"]

        """
        keys_list = []
        if settings:
            for setting in settings:
                stuffs = [([], setting)]
                while stuffs:
                    keys, stuff = stuffs.pop()
                    for key, value in stuff.items():
                        if isinstance(value, dict):
                            stuffs.append((keys + [key], value))
                        else:
                            keys_list.append(keys + [key])
        return keys_list

    def dump(self, file_):
        """Write broadcast variables to the state dump file."""
        pickle.dump(self.settings, file_)
        file_.write("\n")

    def get_db_ops(self):
        """Return the next DB operations from DB queue."""
        ops = self.settings_queue
        self.settings_queue = []
        return ops

    def load(self, pickled_settings):
        """Load broadcast variables from the state dump file."""
        self.settings = pickle.loads(pickled_settings)

    def _get_dump(self):
        """Return broadcast variables as written to the state dump file."""
        return pickle.dumps(self.settings) + "\n"

    @classmethod
    def _get_bad_options(
            cls, prunes, point_strings, namespaces, cancel_keys_list):
        """Return unpruned namespaces and/or point_strings options."""
        cancel_keys_list = [
            tuple(cancel_keys) for cancel_keys in cancel_keys_list]
        bad_options = {
            "point_strings": None, "namespaces": None, "cancel": None}
        # 1. Populate the bad_options dict where applicable.
        # 2. Remove keys if they are found in "prunes".
        # 3. Remove key in bad_options if it becomes empty.
        for opt_name, opt_list, opt_test in [
                ("point_strings", point_strings, cls._point_string_in_prunes),
                ("namespaces", namespaces, cls._namespace_in_prunes),
                ("cancel", cancel_keys_list, cls._cancel_keys_in_prunes)]:
            if opt_list:
                bad_options[opt_name] = set(opt_list)
                for opt in opt_list:
                    if opt_test(prunes, opt):
                        bad_options[opt_name].discard(opt)
                        if not bad_options[opt_name]:
                            break
        for key, value in bad_options.items():
            if value:
                bad_options[key] = list(value)
            else:
                del bad_options[key]
        return bad_options

    @staticmethod
    def _point_string_in_prunes(prunes, point_string):
        """Is point_string pruned?"""
        return point_string in [prune[0] for prune in prunes]

    @staticmethod
    def _namespace_in_prunes(prunes, namespace):
        """Is point_string pruned?"""
        return namespace in [prune[1] for prune in prunes if prune[1:]]

    @staticmethod
    def _cancel_keys_in_prunes(prunes, cancel_keys):
        """Is point_string pruned?"""
        return (list(cancel_keys) in
                [prune[2:] for prune in prunes if prune[2:]])

    def _update_db_queue(self):
        """Update the queue to the runtime DB."""
        this_dump = self._get_dump()
        if this_dump != self.prev_dump:
            now = get_current_time_string(display_sub_seconds=True)
            self.settings_queue.append(RecordBroadcastObject(now, this_dump))
            self.prev_dump = this_dump
