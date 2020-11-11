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

"""cylc install [OPTIONS] ARGS

Install a new suite.


Install the name REG for the suite definition in PATH. The suite server
program can then be started, stopped, and targeted by name REG. (Note that
"cylc run" can also install suites on the fly).

Installation creates a suite run directory "~/cylc-run/REG/" containing a
".service/source" symlink to the suite definition PATH. The .service directory
will also be used for server authentication files at run time.

Suite names can be hierarchical, corresponding to the path under ~/cylc-run.

Examples:
  # Register PATH/flow.cylc as dogs/fido
  # (with run directory ~/cylc-run/dogs/fido)
  $ cylc install dogs/fido PATH

  # Install $PWD/flow.cylc as dogs/fido.
  $ cylc install dogs/fido

  # Install $PWD/flow.cylc as the parent directory
  # name: $(basename $PWD).
  $ cylc install

The same suite can be installed with multiple names; this results in multiple
suite run directories that link to the same suite definition.

To "unregister" a suite, delete or rename its run directory (renaming it under
~/cylc-run effectively re-registers the original suite with the new name).

Use of "--redirect" is required to allow an existing name (and run directory)
to be associated with a different suite definition. This is potentially
dangerous because the new suite will overwrite files in the existing run
directory. You should consider deleting or renaming an existing run directory
rather than just re-use it with another suite."""


import os
import pkg_resources
from pathlib import Path

from cylc.flow.exceptions import PluginError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import get_suite_run_dir
from cylc.flow.suite_files import parse_suite_arg, install
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, prep=True,
        argdoc=[("[REG]", "Suite name"),
                ("[PATH]", "Suite definition directory (defaults to $PWD)")])

    parser.add_option(
        "--redirect", help="Allow an existing suite name and run directory"
                           " to be used with another suite.",
        action="store_true", default=False, dest="redirect")

    return parser


@cli_function(get_option_parser)
def main(parser, opts, flow_name=None, src=None):
    for entry_point in pkg_resources.iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            entry_point.resolve()(opts.source)
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None

    flow_name = install(reg, src, redirect=opts.redirect, rundir=opts.rundir)

    for entry_point in pkg_resources.iter_entry_points(
        'cylc.post_install'
    ):
        try:
            entry_point.resolve()(
                dir_=os.getcwd(),
                opts=opts,
                dest_root=get_suite_run_dir(flow_name)
            )
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.post_install',
                entry_point.name,
                exc
            ) from None


if __name__ == "__main__":
    main()
