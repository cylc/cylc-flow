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
"""Task state properties for display."""

from cylc.task_state import (
    TASK_STATUS_RUNAHEAD,
    TASK_STATUS_WAITING,
    TASK_STATUS_HELD,
    TASK_STATUS_QUEUED,
    TASK_STATUS_READY,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING)

from colorama import Style, Fore, Back


_STATUS_MAP = {
    TASK_STATUS_RUNAHEAD: {
        "ascii_ctrl": Style.BRIGHT + Fore.WHITE + Back.BLUE
    },
    TASK_STATUS_WAITING: {
        "ascii_ctrl": Style.BRIGHT + Fore.CYAN + Back.RESET
    },
    TASK_STATUS_HELD: {
        "ascii_ctrl": Style.BRIGHT + Fore.WHITE + Back.YELLOW
    },
    TASK_STATUS_QUEUED: {
        "ascii_ctrl": Style.BRIGHT + Fore.WHITE + Back.BLUE
    },
    TASK_STATUS_READY: {
        "ascii_ctrl": Style.BRIGHT + Fore.GREEN + Back.RESET
    },
    TASK_STATUS_EXPIRED: {
        "ascii_ctrl": Style.BRIGHT + Fore.WHITE + Back.BLACK
    },
    TASK_STATUS_SUBMITTED: {
        "ascii_ctrl": Style.BRIGHT + Fore.YELLOW + Back.RESET
    },
    TASK_STATUS_SUBMIT_FAILED: {
        "ascii_ctrl": Style.BRIGHT + Fore.BLUE + Back.RESET
    },
    TASK_STATUS_SUBMIT_RETRYING: {
        "ascii_ctrl": Style.BRIGHT + Fore.BLUE + Back.RESET
    },
    TASK_STATUS_RUNNING: {
        "ascii_ctrl": Style.BRIGHT + Fore.WHITE + Back.GREEN
    },
    TASK_STATUS_SUCCEEDED: {
        "ascii_ctrl": Style.NORMAL + Fore.BLACK + Back.RESET
    },
    TASK_STATUS_FAILED: {
        "ascii_ctrl": Style.BRIGHT + Fore.WHITE + Back.RED
    },
    TASK_STATUS_RETRYING: {
        "ascii_ctrl": Style.BRIGHT + Fore.MAGENTA + Back.RESET
    }
}


def extract_group_state(child_states, is_stopped=False):
    """Summarise child states as a group."""
    ordered_states = [TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED,
                      TASK_STATUS_EXPIRED, TASK_STATUS_SUBMIT_RETRYING,
                      TASK_STATUS_RETRYING, TASK_STATUS_RUNNING,
                      TASK_STATUS_SUBMITTED, TASK_STATUS_READY,
                      TASK_STATUS_QUEUED, TASK_STATUS_WAITING,
                      TASK_STATUS_HELD, TASK_STATUS_SUCCEEDED,
                      TASK_STATUS_RUNAHEAD]
    if is_stopped:
        ordered_states = [TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED,
                          TASK_STATUS_RUNNING, TASK_STATUS_SUBMITTED,
                          TASK_STATUS_EXPIRED, TASK_STATUS_READY,
                          TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING,
                          TASK_STATUS_SUCCEEDED, TASK_STATUS_QUEUED,
                          TASK_STATUS_WAITING, TASK_STATUS_HELD,
                          TASK_STATUS_RUNAHEAD]
    for state in ordered_states:
        if state in child_states:
            return state
    return None


def get_status_prop(status, key, subst=None):
    """Return property for a task status."""
    if key == "ascii_ctrl" and subst is not None:
        return "%s%s\033[0m" % (_STATUS_MAP[status][key], subst)
    elif key == "ascii_ctrl":
        return "%s%s\033[0m" % (_STATUS_MAP[status][key], status)
    else:
        return _STATUS_MAP[status][key]
