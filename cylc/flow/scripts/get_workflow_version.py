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

"""cylc get-workflow-version [OPTIONS] ARGS

Find out what version of Cylc a running workflow is using.

To find the version you've invoked at the command line see "cylc version".
"""

from typing import TYPE_CHECKING

from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

if TYPE_CHECKING:
    from optparse import Values


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
def main(parser: COP, options: 'Values', reg: str) -> None:
    reg, _ = parse_reg(reg)
    pclient = get_client(reg, timeout=options.comms_timeout)

    query_kwargs = {
        'request_string': QUERY,
        'variables': {'wFlows': [reg]}
    }

    result = pclient('graphql', query_kwargs)

    for workflow in result['workflows']:
        print(workflow['cylcVersion'])


if __name__ == "__main__":
    main()
