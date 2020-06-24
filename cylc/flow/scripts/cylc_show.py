#!/usr/bin/env python3

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

"""cylc [info] show [OPTIONS] ARGS

Query a running workflow for:
  cylc show REG - workflow metadata
  cylc show REG TASK_NAME - task metadata
  cylc show REG TASK_GLOB - prerequisites and outputs of matched task instances
"""

import json
import sys

from ansimarkup import ansiprint

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.task_id import TaskID
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, noforce=True, multitask=True,
        argdoc=[
            ('REG', 'Suite name'),
            ('[TASK_NAME or TASK_GLOB ...]', 'Task names or match patterns')])

    parser.add_option('--list-prereqs', action="store_true", default=False,
                      help="Print a task's pre-requisites as a list.")

    parser.add_option('--json', action="store_true", default=False,
                      help="Print output in JSON format.")

    return parser


@cli_function(get_option_parser)
def main(_, options, suite, *task_args):
    """Implement "cylc show" CLI."""
    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port,
        options.comms_timeout)
    json_filter = []

    if not task_args:
        # Print suite info.
        suite_info = pclient('get_suite_info')
        if options.json:
            json_filter.append(suite_info)
        else:
            for key, value in sorted(suite_info.items(), reverse=True):
                ansiprint(
                    f'<bold>{key}:</bold> {value or "<m>(not given)</m>"}')

    task_names = [arg for arg in task_args if TaskID.is_valid_name(arg)]
    task_ids = [arg for arg in task_args if TaskID.is_valid_id_2(arg)]

    if task_names:
        results = pclient('get_task_info', {'names': task_names})
        if options.json:
            json_filter.append(results)
        else:
            for task_name, result in sorted(results.items()):
                if len(results) > 1:
                    print("----\nTASK NAME: %s" % task_name)
                for key, value in sorted(result.items(), reverse=True):
                    ansiprint(
                        f'<bold>{key}:</bold> {value or "<m>(not given)</m>"}')

    if task_ids:
        results, bad_items = pclient(
            'get_task_requisites',
            {'task_globs': task_ids, 'list_prereqs': options.list_prereqs}
        )
        if options.json:
            json_filter.append(results)
        else:
            for task_id, result in sorted(results.items()):
                if len(results) > 1:
                    print("----\nTASK ID: %s" % task_id)
                if options.list_prereqs:
                    for prereq in result["prerequisites"]:
                        print(prereq)
                else:
                    for key, value in sorted(
                            result["meta"].items(), reverse=True):
                        ansiprint(
                            f'<bold>{key}:</bold>'
                            f' {value or "<m>(not given)</m>"}')

                    for name, done in [("prerequisites", "satisfied"),
                                       ("outputs", "completed")]:
                        ansiprint(
                            f'\n<bold>{name}</bold>'
                            f' (<red>- => not {done}</red>):')
                        if not result[name]:
                            print('  (None)')
                        for msg, state in result[name]:
                            if state:
                                ansiprint(f'<green>  + {msg}</green>')
                            else:
                                ansiprint(f'<red>  - {msg}</red>')

                    if result["extras"]:
                        print('\nother:')
                        for key, value in result["extras"].items():
                            print('  o  %s ... %s' % (key, value))
            for bad_item in bad_items:
                ansiprint(
                    f"<red>No matching tasks found: {bad_item}\n",
                    file=sys.stderr)
            if bad_items:
                sys.exit(1)

    if options.json:
        print(json.dumps(json_filter, indent=4))


if __name__ == "__main__":
    main()
