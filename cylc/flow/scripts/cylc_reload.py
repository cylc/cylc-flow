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

"""cylc [control] reload [OPTIONS] ARGS

Tell a suite to reload its definition at run time. All settings including task
definitions, with the exception of suite log configuration, can be changed on
reload. Changes to task definitions take effect immediately, unless a task is
already running at reload time.

If the suite was started with Jinja2 template variables set on the command line
(cylc run --set FOO=bar REG) the same template settings apply to the reload
(only changes to the suite.rc file itself are reloaded).

If the modified suite definition does not parse, failure to reload will
be reported but no harm will be done to the running suite."""

import sys
if '--use-ssh' in sys.argv[1:]:
    sys.argv.remove('--use-ssh')
    from cylc.flow.remote import remrun
    if remrun():
        sys.exit(0)

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import prompt, cli_function


def get_option_parser():
    parser = COP(__doc__, comms=True)

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite):
    prompt('Reload %s' % suite, options.force)
    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port,
        options.comms_timeout)
    pclient('reload_suite')


if __name__ == "__main__":
    main()
