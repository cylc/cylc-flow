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

"""cylc set-verbosity [OPTIONS] ARGS

Change the logging severity level of a running workflow.

Only messages at or above the chosen severity level will be logged; for
example, if you choose WARNING, only warnings and critical messages will be
logged.
"""

from optparse import Values

from cylc.flow import LOG_LEVELS
from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $level: LogLevels!,
) {
  setVerbosity (
    workflows: $wFlows,
    level: $level,
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__, comms=True,
        argdoc=[
            ('REG', 'Workflow name'),
            ('LEVEL', ', '.join(LOG_LEVELS.keys()))
        ]
    )

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', reg: str, severity_str: str) -> None:
    try:
        severity = LOG_LEVELS[severity_str]
    except KeyError:
        parser.error("Illegal logging level, %s" % severity_str)

    reg, _ = parse_reg(reg)
    pclient = get_client(reg, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [reg],
            'level': severity,
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
