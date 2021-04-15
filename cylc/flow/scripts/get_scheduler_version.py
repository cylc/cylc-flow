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

"""cylc get-suite-version [OPTIONS] ARGS

Find out what version of Cylc a running scheduler is using.

To find the version you've invoked at the command line see "cylc version".
"""

from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function

QUERY = '''
query ($wFlows: [ID]) {
  workflows(ids: $wFlows) {
    id
    name
    owner
    cylcVersion
  }
}
'''


def get_option_parser():
    parser = COP(__doc__, comms=True)

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite):
    pclient = get_client(suite, timeout=options.comms_timeout)

    query_kwargs = {
        'request_string': QUERY,
        'variables': {'wFlows': [suite]}
    }

    result = pclient('graphql', query_kwargs)

    for workflow in result['workflows']:
        print(workflow['cylcVersion'])


if __name__ == "__main__":
    main()
