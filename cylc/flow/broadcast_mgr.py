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
"""Manage broadcast (and external trigger broadcast)."""

import re
from copy import deepcopy
from threading import RLock

from cylc.flow import LOG
from cylc.flow.broadcast_report import (
    CHANGE_FMT,
    CHANGE_PREFIX_SET,
    get_broadcast_change_report,
    get_broadcast_bad_options_report,
)
from cylc.flow.cfgspec.workflow import SPEC
from cylc.flow.id import Tokens
from cylc.flow.cycling.loader import get_point, standardise_point_string
from cylc.flow.exceptions import PointParsingError
from cylc.flow.parsec.validate import cylc_config_validate

ALL_CYCLE_POINTS_STRS = ["*", "all-cycle-points", "all-cycles"]


def addict(target, source):
    """Recursively add source dict to target dict."""
    for key, val in source.items():
        if isinstance(val, dict):
            if key not in target:
                target[key] = {}
            addict(target[key], val)
        else:
            target[key] = val


class BroadcastMgr:
    """Manage broadcast.

    Broadcast settings are stored in the form:
        self.broadcasts['*']['root'] = {'environment': {'FOO': 'bar'}}
        self.broadcasts['20100808T06Z']['root'] = {'script': 'stuff'}
    """

    REC_SECTION = re.compile(r"\[([^\]]+)\]")

    def __init__(self, workflow_db_mgr, data_store_mgr):
        self.workflow_db_mgr = workflow_db_mgr
        self.data_store_mgr = data_store_mgr
        self.linearized_ancestors = {}
        self.broadcasts = {}
        self.ext_triggers = {}  # Can use collections.Counter in future
        self.lock = RLock()

    def check_ext_triggers(self, itask, ext_trigger_queue):
        """Get queued ext trigger messages and try to satisfy itask.

        Ext-triggers are pushed by the remote end, so we can check for
        new messages and satisfy dependent tasks at the same time.
        Return True if itask has a newly satisfied ext-trigger.
        """
        while not ext_trigger_queue.empty():
            ext_trigger = ext_trigger_queue.get_nowait()
            self.ext_triggers.setdefault(ext_trigger, 0)
            self.ext_triggers[ext_trigger] += 1
        return self._match_ext_trigger(itask)

    def clear_broadcast(
            self, point_strings=None, namespaces=None, cancel_settings=None):
        """Clear broadcasts globally, or for listed namespaces and/or points.

        Return a tuple (modified_settings, bad_options), where:
        * modified_settings is similar to the return value of the "put" method,
          but for removed broadcasts.
        * bad_options is a dict in the form:
              {"point_strings": ["20020202", ..."], ...}
          The dict is only populated if there are options not associated with
          previous broadcasts. The keys can be:
          * point_strings: a list of bad point strings.
          * namespaces: a list of bad namespaces.
          * cancel: a list of tuples. Each tuple contains the keys of a bad
            setting.
        """
        # If cancel_settings defined, only clear specific broadcasts
        cancel_keys_list = self._settings_to_keys_list(cancel_settings)

        # Clear broadcasts
        modified_settings = []
        with self.lock:
            for point_string, point_string_settings in self.broadcasts.items():
                if point_strings and point_string not in point_strings:
                    continue
                for namespace, namespace_settings in (
                        point_string_settings.items()):
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
        self.workflow_db_mgr.put_broadcast(modified_settings, is_cancel=True)
        LOG.info(
            get_broadcast_change_report(modified_settings, is_cancel=True))
        if bad_options:
            LOG.error(get_broadcast_bad_options_report(bad_options))
        if modified_settings:
            self.data_store_mgr.delta_broadcast()
        return modified_settings, bad_options

    def expire_broadcast(self, cutoff=None, **kwargs):
        """Clear all broadcasts targeting cycle points earlier than cutoff."""
        point_strings = []
        cutoff_point = None
        if cutoff is not None:
            cutoff_point = get_point(str(cutoff))
        with self.lock:
            for point_string in self.broadcasts:
                if cutoff_point is None or (
                        point_string not in ALL_CYCLE_POINTS_STRS and
                        get_point(point_string) < cutoff_point):
                    point_strings.append(point_string)
        if not point_strings:
            return (None, {"expire": [cutoff]})
        return self.clear_broadcast(point_strings=point_strings, **kwargs)

    def get_broadcast(self, task_id=None):
        """Retrieve all broadcast variables that target a given task ID."""
        if task_id == "None":
            task_id = None
        if not task_id:
            # all broadcasts requested
            return self.broadcasts
        try:
            tokens = Tokens(task_id, relative=True)
            name = tokens['task']
            point_string = tokens['cycle']
        except ValueError:
            raise Exception("Can't split task_id %s" % task_id)

        ret = {}
        # The order is:
        #    all:root -> all:FAM -> ... -> all:task
        # -> tag:root -> tag:FAM -> ... -> tag:task
        for cycle in ALL_CYCLE_POINTS_STRS + [point_string]:
            if cycle not in self.broadcasts:
                continue
            for namespace in reversed(self.linearized_ancestors[name]):
                if namespace in self.broadcasts[cycle]:
                    addict(ret, self.broadcasts[cycle][namespace])
        return ret

    def load_db_broadcast_states(self, row_idx, row):
        """Load broadcast variables from runtime DB broadcast states row."""
        if row_idx == 0:
            LOG.info("LOADING broadcast states")
        point, namespace, key, value = row
        sections = []
        cur_key = key
        if "]" in cur_key:
            sections = self.REC_SECTION.findall(cur_key)
            cur_key = cur_key.rsplit(r"]", 1)[-1]
        with self.lock:
            self.broadcasts.setdefault(point, {})
            self.broadcasts[point].setdefault(namespace, {})
            dict_ = self.broadcasts[point][namespace]
            for section in sections:
                dict_.setdefault(section, {})
                dict_ = dict_[section]
            dict_[cur_key] = value
        LOG.info(CHANGE_FMT.strip() % {
            "change": CHANGE_PREFIX_SET,
            "point": point,
            "namespace": namespace,
            "key": key,
            "value": value})

    def post_load_db_coerce(self):
        """Coerce DB loaded values to config objects, i.e. DurationFloat."""
        for namespaces in self.broadcasts.values():
            for settings in namespaces.values():
                cylc_config_validate(settings, SPEC['runtime']['__MANY__'])

    def _match_ext_trigger(self, itask):
        """Match external triggers for a waiting task proxy."""
        if not self.ext_triggers or not itask.state.external_triggers:
            return False
        for trig, satisfied in list(itask.state.external_triggers.items()):
            if satisfied:
                continue
            for qmsg, qid in self.ext_triggers.copy():
                if trig != qmsg:
                    continue
                # Matched.
                point_string = itask.tokens['cycle']
                # Set trigger satisfied.
                itask.state.external_triggers[trig] = True
                # Broadcast the event ID to the cycle point.
                if qid is not None:
                    self.put_broadcast(
                        [point_string],
                        ['root'],
                        [{'environment': {'CYLC_EXT_TRIGGER_ID': qid}}],
                    )
                # Create data-store delta
                self.data_store_mgr.delta_task_ext_trigger(
                    itask, qid, qmsg, True)
                self.ext_triggers[(qmsg, qid)] -= 1
                if not self.ext_triggers[(qmsg, qid)]:
                    del self.ext_triggers[(qmsg, qid)]
                return True
        return False

    def put_broadcast(
            self, point_strings=None, namespaces=None, settings=None):
        """Add new broadcast settings (server side interface).

        Return a tuple (modified_settings, bad_options) where:
          modified_settings is list of modified settings in the form:
            [("20200202", "foo", {"script": "true"}, ...]
          bad_options is as described in the docstring for self.clear().
        """
        modified_settings = []
        bad_point_strings = []
        bad_namespaces = []

        with self.lock:
            for setting in settings:
                for point_string in point_strings:
                    # Standardise the point and check its validity.
                    bad_point = False
                    try:
                        point_string = standardise_point_string(point_string)
                    except PointParsingError:
                        if point_string != '*':
                            bad_point_strings.append(point_string)
                            bad_point = True
                    if not bad_point and point_string not in self.broadcasts:
                        self.broadcasts[point_string] = {}
                    for namespace in namespaces:
                        if namespace not in self.linearized_ancestors:
                            bad_namespaces.append(namespace)
                        elif not bad_point:
                            if namespace not in self.broadcasts[point_string]:
                                self.broadcasts[point_string][namespace] = {}
                            # Keep saved/reported setting as workflow
                            # config format.
                            modified_settings.append(
                                (point_string, namespace, deepcopy(setting))
                            )
                            # Coerce setting to cylc runtime object,
                            # i.e. str to  DurationFloat.
                            cylc_config_validate(
                                setting,
                                SPEC['runtime']['__MANY__']
                            )
                            addict(
                                self.broadcasts[point_string][namespace],
                                setting
                            )

        # Log the broadcast
        self.workflow_db_mgr.put_broadcast(modified_settings)
        LOG.info(get_broadcast_change_report(modified_settings))

        bad_options = {}
        if bad_point_strings:
            bad_options["point_strings"] = bad_point_strings
        if bad_namespaces:
            bad_options["namespaces"] = bad_namespaces
        if modified_settings:
            self.data_store_mgr.delta_broadcast()
        return modified_settings, bad_options

    @staticmethod
    def _cancel_keys_in_prunes(prunes, cancel_keys):
        """Is cancel_keys pruned?"""
        return (list(cancel_keys) in
                [prune[2:] for prune in prunes if prune[2:]])

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
        for key, value in list(bad_options.copy().items()):
            if value:
                bad_options[key] = list(value)
            else:
                del bad_options[key]
        return bad_options

    @staticmethod
    def _namespace_in_prunes(prunes, namespace):
        """Is namespace pruned?"""
        return namespace in [prune[1] for prune in prunes if prune[1:]]

    @staticmethod
    def _point_string_in_prunes(prunes, point_string):
        """Is point_string pruned?"""
        return point_string in [prune[0] for prune in prunes]

    def _prune(self):
        """Remove empty leaves left by unsetting broadcast values.

        Return a list of pruned broadcasts in the form:

        [
            ["20200202", "foo", "script"],
            ["20020202", "bar", "environment", "BAR"],
        ]
        """
        with self.lock:
            prunes = []
            stuff_stack = [([], self.broadcasts, True)]
            while stuff_stack:
                keys, stuff, is_new = stuff_stack.pop()
                if is_new:
                    stuff_stack.append((keys, stuff, False))
                    for key, value in stuff.items():
                        if isinstance(value, dict):
                            stuff_stack.append((keys + [key], value, True))
                else:
                    for key, value in stuff.copy().items():
                        if value in [None, {}]:
                            del stuff[key]
                            prunes.append(keys + [key])
            return prunes

    @staticmethod
    def _settings_to_keys_list(broadcasts):
        """Return a list containing each setting dict keys.

        E.g. Each setting in broadcasts may look like:
        {"foo": {"bar": {"baz": 1}}}

        An element of the returned list will look like:
        ["foo", "bar", "baz"]

        """
        keys_list = []
        if broadcasts:
            for broadcast in broadcasts:
                stuff_stack = [([], broadcast)]
                while stuff_stack:
                    keys, stuff = stuff_stack.pop()
                    for key, value in stuff.items():
                        if isinstance(value, dict):
                            stuff_stack.append((keys + [key], value))
                        else:
                            keys_list.append(keys + [key])
        return keys_list
