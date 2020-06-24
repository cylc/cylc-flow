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

"""cylc [discovery] check-versions [OPTIONS] ARGS

Check the version of cylc invoked on each of SUITE's task host platforms when
CYLC_VERSION is set to *the version running this command line tool*.
Different versions are reported but are not considered an error unless the
-e|--error option is specified, because different cylc versions from 6.0.0
onward should at least be backward compatible.

It is recommended that cylc versions be installed in parallel and access
configured via the cylc version wrapper as described in the cylc INSTALL
file and User Guide. This must be done on suite and task hosts. Users then get
the latest installed version by default, or (like tasks) a particular version
if $CYLC_VERSION is defined.

Use -v/--verbose to see the command invoked to determine the remote version
(all remote cylc command invocations will be of the same form, which may be
site dependent -- see cylc global config documentation."""

import sys

import cylc.flow.flags
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.cylc_subproc import Popen, PIPE, DEVNULL
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.config import SuiteConfig
from cylc.flow.platforms import forward_lookup
from cylc.flow.remote import construct_platform_ssh_cmd
from cylc.flow.suite_files import parse_suite_arg
from cylc.flow.templatevars import load_template_vars
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(__doc__, prep=True, jset=True)

    parser.add_option(
        "-e", "--error", help="Exit with error status "
        "if " + CYLC_VERSION + " is not available on all remote platforms.",
        action="store_true", default=False, dest="error")

    return parser


@cli_function(get_option_parser)
def main(_, options, *args):
    # suite name or file path
    suite, suiterc = parse_suite_arg(options, args[0])

    # extract task host platforms from the suite
    config = SuiteConfig(
        suite,
        suiterc,
        options,
        load_template_vars(options.templatevars, options.templatevars_file))

    platforms = {
        config.get_config(['runtime', name, 'platform'])
        for name in config.get_namespace_list('all tasks')
    } ^ {None, 'localhost'}

    # When "suite run hosts" are formalised as "flow platforms"
    # we can substitute `localhost` for this, in the mean time
    # we will have to assume that flow hosts are configured correctly.

    verbose = cylc.flow.flags.verbose

    # get the cylc version on each platform
    versions = {}
    for platform_name in sorted(platforms):
        platform = forward_lookup(platform_name)
        cmd = construct_platform_ssh_cmd(['version'], platform)
        if verbose:
            print(cmd)
        proc = Popen(cmd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate()
        out = out.decode()
        err = err.decode()
        if proc.wait() == 0:
            if verbose:
                print("   %s" % out)
            versions[platform_name] = out.strip()
        else:
            versions[platform_name] = f'ERROR: {err.strip()}'

    # report results
    max_len = max((len(platform_name) for platform_name in platforms))
    print(f'{"platform".rjust(max_len)}: cylc version')
    print('-' * (max_len + 14))
    for platform_name, result in versions.items():
        print(f'{platform_name.rjust(max_len)}: {result}')
    if all((version == CYLC_VERSION for version in versions.values())):
        exit = 0
    elif options.error:
        exit = 1
    else:
        exit = 0
    sys.exit(exit)
