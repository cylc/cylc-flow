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
"""Provide a function to report modification to broadcast settings."""


BAD_OPTIONS_FMT = "\n  --%s=%s"
BAD_OPTIONS_TITLE = "ERROR: No broadcast to cancel/clear for these options:"
BAD_OPTIONS_TITLE_SET = "ERROR: Invalid broadcast set options:"
CHANGE_FMT = "\n%(change)s [%(namespace)s.%(point)s] %(key)s=%(value)s"
CHANGE_PREFIX_CANCEL = "-"
CHANGE_PREFIX_SET = "+"
CHANGE_TITLE_CANCEL = "Broadcast cancelled:"
CHANGE_TITLE_SET = "Broadcast set:"


def get_broadcast_bad_options_report(bad_options, is_set=False):
    """Return a string to report bad options for broadcast cancel/clear."""
    if not bad_options:
        return None
    if is_set:
        msg = BAD_OPTIONS_TITLE_SET
    else:
        msg = BAD_OPTIONS_TITLE
    for key, values in sorted(bad_options.items()):
        for value in values:
            if isinstance(value, tuple):
                value_str = ""
                values = list(value)
                while values:
                    val = values.pop(0)
                    if values:
                        value_str += "[" + val + "]"
                    else:
                        value_str += val
            else:
                value_str = value
            msg += BAD_OPTIONS_FMT % (key, value_str)
    return msg


def get_broadcast_change_iter(modified_settings, is_cancel=False):
    """Return an iterator of broadcast changes.

    Each broadcast change is a dict with keys:
    change, point, namespace, key, value

    """
    if not modified_settings:
        return
    if is_cancel:
        change = CHANGE_PREFIX_CANCEL
    else:
        change = CHANGE_PREFIX_SET
    for modified_setting in sorted(modified_settings):
        point, namespace, setting = modified_setting
        value = setting
        keys_str = ""
        while isinstance(value, dict):
            key, value = value.items()[0]
            if isinstance(value, dict):
                keys_str += "[" + key + "]"
            else:
                keys_str += key
                yield {
                    "change": change,
                    "point": point,
                    "namespace": namespace,
                    "key": keys_str,
                    "value": str(value)}


def get_broadcast_change_report(modified_settings, is_cancel=False):
    """Return a string for reporting modification to broadcast settings."""
    if not modified_settings:
        return ""
    if is_cancel:
        change = CHANGE_PREFIX_CANCEL
        msg = CHANGE_TITLE_CANCEL
    else:
        change = CHANGE_PREFIX_SET
        msg = CHANGE_TITLE_SET
    for broadcast_change in get_broadcast_change_iter(
            modified_settings, is_cancel):
        msg += CHANGE_FMT % broadcast_change
    return msg
