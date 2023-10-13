#!/usr/bin/env python3
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
"""The cylc terminal user interface (Tui)."""

from cylc.flow.task_state import (
    TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED
)

TUI = """
                           _,@@@@@@.
                         <=@@@, `@@@@@.
                            `-@@@@@@@@@@@'
                               :@@@@@@@@@@.
                              (.@@@@@@@@@@@
                             ( '@@@@@@@@@@@@.
                            ;.@@@@@@@@@@@@@@@
                          '@@@@@@@@@@@@@@@@@@,
                        ,@@@@@@@@@@@@@@@@@@@@'
                      :.@@@@@@@@@@@@@@@@@@@@@.
                    .@@@@@@@@@@@@@@@@@@@@@@@@.
                  '@@@@@@@@@@@@@@@@@@@@@@@@@.
                ;@@@@@@@@@@@@@@@@@@@@@@@@@@@
               .@@@@@@@@@@@@@@@@@@@@@@@@@@.
              .@@@@@@@@@@@@@@@@@@@@@@@@@@,
             .@@@@@@@@@@@@@@@@@@@@@@@@@'
            .@@@@@@@@@@@@@@@@@@@@@@@@'     ,
          :@@@@@@@@@@@@@@@@@@@@@..''';,,,;::-
         '@@@@@@@@@@@@@@@@@@@.        `.   `
        .@@@@@@.: ,.@@@@@@@.            `
      :@@@@@@@,         ;.@,
     '@@@@@@.              `@'
    .@@@@@@;                ;-,
  ;@@@@@@.                   ...,
,,; ,;;                      ; ; ;
"""

# default foreground and background colours
# NOTE: set to default to allow user defined terminal theming
FORE = 'default'
BACK = 'default'

# workflow state colour
WORKFLOW_COLOURS = {
    'running': ('light blue', BACK),
    'paused': ('brown', BACK),
    'stopping': ('light magenta', BACK),
    'stopped': ('light red', BACK),
    'error': ('light red', BACK, 'bold')
}

# unicode task icons
TASK_ICONS = {
    f'{TASK_STATUS_WAITING}': '\u25cb',
    f'{TASK_STATUS_PREPARING}': '\u229A',
    f'{TASK_STATUS_SUBMITTED}': '\u2299',
    f'{TASK_STATUS_RUNNING}': '\u2299',
    f'{TASK_STATUS_RUNNING}:0': '\u2299',
    f'{TASK_STATUS_RUNNING}:25': '\u25D4',
    f'{TASK_STATUS_RUNNING}:50': '\u25D1',
    f'{TASK_STATUS_RUNNING}:75': '\u25D5',
    f'{TASK_STATUS_SUCCEEDED}': '\u25CF',
    f'{TASK_STATUS_EXPIRED}': '\u25CC',
    f'{TASK_STATUS_SUBMIT_FAILED}': '\u2298',
    f'{TASK_STATUS_FAILED}': '\u2297'
}

# unicode modifiers for special task states
TASK_MODIFIERS = {
    'held': '\u030E',
    'queued': '\u033F',
    'runahead': '\u030A'
}

# unicode job icon
JOB_ICON = '\u25A0'

# job colour coding
JOB_COLOURS = {
    'submitted': 'dark cyan',
    'running': 'light blue',
    'succeeded': 'dark green',
    'failed': 'light red',
    'submit-failed': 'light magenta',
}


class Bindings:
    """Represets key bindings for the Tui app."""

    def __init__(self):
        self.bindings = []
        self.groups = {}

    def bind(self, keys, group, desc, callback):
        """Register a key binding.

        Args:
            keys:
                The keys to bind.
            group:
                The group to which this binding should belong.
            desc:
                Description for this binding, used to generate help.
            callback:
                The thing to call when this binding is pressed.

        """
        if group not in self.groups:
            raise ValueError(f'Group {group} not registered.')
        binding = {
            'keys': keys,
            'group': group,
            'desc': desc,
            'callback': callback
        }
        self.bindings.append(binding)
        self.groups[group]['bindings'].append(binding)

    def add_group(self, group, desc):
        """Add a new binding group.

        Args:
            group:
                The name of the group.
            desc:
                A description of the group, used to generate help.

        """
        self.groups[group] = {
            'name': group,
            'desc': desc,
            'bindings': []
        }

    def __iter__(self):
        return iter(self.bindings)

    def list_groups(self):
        """List groups and the bindings in them.

        Yields:
            (group_name, [binding, ...])

        """
        for name, group in self.groups.items():
            yield (
                group,
                [
                    binding
                    for binding in self.bindings
                    if binding['group'] == name
                ]
            )
