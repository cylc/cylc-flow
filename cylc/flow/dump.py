# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Utility for "cylc dump"."""


def dump_to_stdout(states, sort_by_cycle=False, flow=False):
    """Print states in "cylc dump" format to STDOUT.

    states = {
        "task_id": {
            "name": name,
            "label": point,
            "flow": flow_label,
            "state": state,
        # ...
    }
    """
    lines = []
    for item in states.values():
        if sort_by_cycle:
            values = [
                item['label'],
                item['name'],
                item['state']]
            if flow:
                values.append(item['flow_label'])
            values.append('held' if item['is_held'] else 'unheld')
        else:
            values = [
                item['name'],
                item['label']]
            if flow:
                values.append(item['flow_label'])
            values.append(item['state'])
            values.append('held' if item['is_held'] else 'unheld')
        lines.append(', '.join(values))

    lines.sort()
    for line in lines:
        print(line)
