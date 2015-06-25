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
import logging
import cPickle as pickle

from cylc.broadcast_report import (
    get_broadcast_change_iter,
    get_broadcast_change_report,
    get_broadcast_bad_options_report)
from cylc.cycling.loader import get_point, standardise_point_string
import cylc.flags
from cylc.network.pyro_base import PyroClient, PyroServer
from cylc.rundb import CylcSuiteDAO
from cylc.task_id import TaskID
from cylc.wallclock import get_current_time_string

PYRO_BCAST_OBJ_NAME = 'broadcast_receiver'


class BroadcastServer(PyroServer):
    """Server-side suite broadcast interface.

    Examples:
    self.settings['*']['root'] = {'environment': {'FOO': 'bar'}}
    self.settings['20100808T06Z']['root'] = {'command scripting': 'stuff'}
    """

    _INSTANCE = None
    ALL_CYCLE_POINTS_STRS = ["*", "all-cycle-points", "all-cycles"]
    TABLE_BROADCAST_EVENTS = CylcSuiteDAO.TABLE_BROADCAST_EVENTS
    TABLE_BROADCAST_STATES = CylcSuiteDAO.TABLE_BROADCAST_STATES

    @classmethod
    def get_inst(cls, linearized_ancestors=None):
        """Return a singleton instance.

        On 1st call, instantiate the singleton.
        Argument linearized_ancestors is only relevant on 1st call.

        """
        if cls._INSTANCE is None:
            cls._INSTANCE = cls(linearized_ancestors)
        return cls._INSTANCE

    def __init__(self, linearized_ancestors):
        super(BroadcastServer, self).__init__()
        self.log = logging.getLogger('main')
        self.settings = {}
        self.db_inserts_map = {
            self.TABLE_BROADCAST_EVENTS: [],
            self.TABLE_BROADCAST_STATES: []}
        self.db_deletes_map = {
            self.TABLE_BROADCAST_STATES: []}
        self.linearized_ancestors = linearized_ancestors

    def _prune(self):
        """Remove empty leaves left by unsetting broadcast values.

        Return a list of pruned settings in the form:

        [
            ["20200202", "foo", "command scripting"],
            ["20020202", "bar", "environment", "BAR"],
        ]
        """
        prunes = []
        stuff_stack = [([], self.settings, True)]
        while stuff_stack:
            keys, stuff, is_new = stuff_stack.pop()
            if is_new:
                stuff_stack.append((keys, stuff, False))
                for key, value in stuff.items():
                    if isinstance(value, dict):
                        stuff_stack.append((keys + [key], value, True))
            else:
                for key, value in stuff.items():
                    if value in [None, {}]:
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
                target[key] = source[key]

    def put(self, point_strings, namespaces, settings):
        """Add new broadcast settings.

        Return a tuple (modified_settings, bad_options) where:
          modified_settings is list of modified settings in the form:
            [("20200202", "foo", {"command scripting": "true"}, ...]
          bad_options is as described in the docstring for self.clear().
        """
        modified_settings = []
        bad_point_strings = []
        bad_namespaces = []

        for setting in settings:
            for point_string in point_strings:
                # Standardise the point and check its validity.
                bad_point = False
                try:
                    point_string = standardise_point_string(point_string)
                except Exception as exc:
                    if point_string != '*':
                        bad_point_strings.append(point_string)
                        bad_point = True
                if not bad_point and point_string not in self.settings:
                    self.settings[point_string] = {}
                for namespace in namespaces:
                    if namespace not in self.linearized_ancestors:
                        bad_namespaces.append(namespace)
                    elif not bad_point:
                        if namespace not in self.settings[point_string]:
                            self.settings[point_string][namespace] = {}
                        self._addict(
                            self.settings[point_string][namespace], setting)
                        modified_settings.append(
                            (point_string, namespace, setting))

        # Log the broadcast
        self._append_db_queue(modified_settings)
        self.log.info(get_broadcast_change_report(modified_settings))

        bad_options = {}
        if bad_point_strings:
            bad_options["point_strings"] = bad_point_strings
        if bad_namespaces:
            bad_options["namespaces"] = bad_namespaces
        return modified_settings, bad_options

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
                stuff_stack = [([], namespace_settings)]
                while stuff_stack:
                    keys, stuff = stuff_stack.pop()
                    for key, value in stuff.items():
                        if isinstance(value, dict):
                            stuff_stack.append((keys + [key], value))
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
        self._append_db_queue(modified_settings, is_cancel=True)
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
                stuff_stack = [([], setting)]
                while stuff_stack:
                    keys, stuff = stuff_stack.pop()
                    for key, value in stuff.items():
                        if isinstance(value, dict):
                            stuff_stack.append((keys + [key], value))
                        else:
                            keys_list.append(keys + [key])
        return keys_list

    def dump(self, file_):
        """Write broadcast variables to the state dump file."""
        pickle.dump(self.settings, file_)
        file_.write("\n")

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
        """Is namespace pruned?"""
        return namespace in [prune[1] for prune in prunes if prune[1:]]

    @staticmethod
    def _cancel_keys_in_prunes(prunes, cancel_keys):
        """Is cancel_keys pruned?"""
        return (list(cancel_keys) in
                [prune[2:] for prune in prunes if prune[2:]])

    def _append_db_queue(self, modified_settings, is_cancel=False):
        """Update the queue to the runtime DB."""
        now = get_current_time_string(display_sub_seconds=True)
        for broadcast_change in (
                get_broadcast_change_iter(modified_settings, is_cancel)):
            broadcast_change["time"] = now
            self.db_inserts_map[self.TABLE_BROADCAST_EVENTS].append(
                broadcast_change)
            if is_cancel:
                self.db_deletes_map[self.TABLE_BROADCAST_STATES].append({
                    "point": broadcast_change["point"],
                    "namespace": broadcast_change["namespace"],
                    "key": broadcast_change["key"]})
            else:
                self.db_inserts_map[self.TABLE_BROADCAST_STATES].append({
                    "point": broadcast_change["point"],
                    "namespace": broadcast_change["namespace"],
                    "key": broadcast_change["key"],
                    "value": broadcast_change["value"]})


class BroadcastClient(PyroClient):
    """Client-side suite broadcast interface."""

    target_server_object = PYRO_BCAST_OBJ_NAME

    def broadcast(self, command, *command_args):
        """CLI suite broadcast interface."""
        try:
            self._report(command)
            try:
                return getattr(self.pyro_proxy, command)(*command_args)
            except AttributeError:
                sys.exit("Illegal broadcast command: %s" % command)
        except Exception as exc:
            if cylc.flags.debug:
                raise
            sys.exit(exc)
