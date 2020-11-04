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

"""cylc reload [OPTIONS] ARGS

Reload the configuration of a running suite.

Tell a suite to reload its definition at run time. All settings including task
definitions, with the exception of suite log configuration, can be changed on
reload. Changes to task definitions take effect immediately, unless a task is
already running at reload time.

If the suite was started with Jinja2 template variables set on the command line
(cylc run --set FOO=bar REG) the same template settings apply to the reload
(only changes to the flow.cylc file itself are reloaded).

If the modified suite definition does not parse, failure to reload will
be reported but no harm will be done to the running suite."""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import cli_function

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!
) {
  reload (
    workflows: $wFlows
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(__doc__, comms=True)

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite):
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [suite],
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
