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

"""cylc checkpoint [OPTIONS] ARGS

Tell suite to checkpoint its current state.
"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import cli_function

MUTATION = '''
mutation (
    $wFlows: [WorkflowID]!,
    $cName: String!
) {
  checkpoint (
    workflows: $wFlows,
    name: $cName
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(__doc__, comms=True, argdoc=[
        ("REG", "Suite name"),
        ("CHECKPOINT-NAME", "Checkpoint name")])

    return parser


@cli_function(get_option_parser)
def main(_, options, suite, name):
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [suite],
            'cName': name,
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
