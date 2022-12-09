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

"""cylc check-versions [OPTIONS] ARGS

Check that Cylc versions match on different platforms.

Check that the remote versions of Cylc invoked on each of the platforms used by
a workflow matches the version this script is run with.

Note:
  Cylc supports multiple parallel installations at different versions via the
  Cylc wrapper script. For more information see the installation section of the
  documentation.

Use -v/--verbose to see the command invoked to determine the remote version
(all remote Cylc command invocations will be of the same form, which may be
site dependent -- see cylc global config documentation.
"""

import sys
from typing import TYPE_CHECKING

import cylc.flow.flags
from cylc.flow.option_parsers import (
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.cylc_subproc import procopen, PIPE, DEVNULL
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import NoHostsError
from cylc.flow.id_cli import parse_id
from cylc.flow.platforms import get_platform, get_host_from_platform
from cylc.flow.remote import construct_ssh_cmd
from cylc.flow.templatevars import load_template_vars
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    parser = COP(
        __doc__,
        jset=True,
        argdoc=[WORKFLOW_ID_OR_PATH_ARG_DOC],
    )

    parser.add_option(
        "-e", "--error",
        help=(
            f"Exit with error status if {CYLC_VERSION} is not available "
            "on all remote platforms."
        ),
        action="store_true", default=False, dest="error"
    )

    return parser


@cli_function(get_option_parser)
def main(_, options: 'Values', *ids) -> None:
    workflow_id, _, flow_file = parse_id(
        *ids,
        src=True,
        constraint='workflows',
    )

    # extract task host platforms from the workflow_id
    config = WorkflowConfig(
        workflow_id,
        flow_file,
        options,
        load_template_vars(options.templatevars, options.templatevars_file))

    platforms = {
        config.get_config(['runtime', name, 'platform'])
        for name in config.get_namespace_list('all tasks')
    } - {None, 'localhost'}

    # When "workflow run hosts" are formalised as "flow platforms"
    # we can substitute `localhost` for this, in the mean time
    # we will have to assume that flow hosts are configured correctly.

    if not platforms:
        sys.exit(0)

    verbose = cylc.flow.flags.verbosity > 0
    versions = check_versions(platforms, verbose)
    report_results(platforms, versions, options.error)


def check_versions(platforms, verbose):
    # get the cylc version on each platform
    versions = {}
    for platform_name in sorted(platforms):
        platform = get_platform(platform_name)
        try:
            host = get_host_from_platform(
                platform,
                bad_hosts=None
            )
        except NoHostsError:
            print(
                f'Could not connect to {platform["name"]}',
                file=sys.stderr
            )
            continue
        cmd = construct_ssh_cmd(
            ['version'],
            platform,
            host
        )
        if verbose:
            print(cmd)
        proc = procopen(cmd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate()
        out = out.decode()
        err = err.decode()
        if proc.wait() == 0:
            if verbose:
                print("   %s" % out)
            versions[platform_name] = out.strip()
        else:
            versions[platform_name] = f'ERROR: {err.strip()}'
    return versions


def report_results(platforms, versions, exit_error):
    # report results
    max_len = max((len(platform_name) for platform_name in platforms))
    print(f'{"platform".rjust(max_len)}: cylc version')
    print('-' * (max_len + 14))
    for platform_name, result in versions.items():
        print(f'{platform_name.rjust(max_len)}: {result}')
    if all((version == CYLC_VERSION for version in versions.values())):
        ret_code = 0
    elif exit_error:
        ret_code = 1
    else:
        ret_code = 0
    sys.exit(ret_code)
