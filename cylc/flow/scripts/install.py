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

Install a new workflow.

Install the name REG. The workflow server program can then be started, stopped,
and targeted by name REG. (Note that "cylc run" can also install workflows on
the fly).

Installation creates a workflow run directory "~/cylc-run/REG/", with a run
directory "~/cylc-run/REG/run1" containing a "_cylc-install/source" symlink to
the source directory.
Any files or directories (excluding .git, .svn) from the source directory are
copied to the new run directory.
A .service directory will also be created and used for server authentication
files at run time.


Workflow names can be hierarchical, corresponding to the path under ~/cylc-run.

Examples:
  # Install workflow dogs/fido from $PWD
  # (with run directory ~/cylc-run/dogs/fido/run1)
  # (if "run1" exists this will increment)
  $ cylc install dogs/fido

  # Install $PWD/flow.cylc with specified flow name: fido
  # (with run directory ~/cylc-run/fido/run1)
  $ cylc install --flow-name=fido

  # Install PATH/TO/FLOW/flow.cylc
  $ cylc install --directory=PATH/TO/FLOW

  # Install cats/flow.cylc
  # (with run directory ~/cylc-run/cats/paws)
  # overriding the run1, run2, run3 etc structure.
  $ cylc install --run-name=paws

The same workflow can be installed with multiple names; this results in
multiple workflow run directories that link to the same suite definition.

"""


import os
import pkg_resources

from cylc.flow.exceptions import PluginError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.suite_files import install_workflow
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, prep=True,
        argdoc=[("[REG]", "Workflow name")
                ])

    parser.add_option(
        "--flow-name",
        help="Install into ~/cylc-run/flow-name/runN ",
        action="store",
        metavar="MY_FLOW",
        default=None,
        dest="flow_name")

    parser.add_option(
        "--directory", "-C",
        help=(
            "Install the workflow found in path specfied."
            " This defaults to $PWD."),
        action="store",
        metavar="PATH/TO/FLOW",
        default=None,
        dest="source")

    parser.add_option(
        "--run-name",
        help="Name the run.",
        action="store",
        metavar="RUN_NAME",
        default=None,
        dest="run_name")

    parser.add_option(
        "--no-run-name",
        help="Install the workflow directly into ~/cylc-run/$(basename $PWD)",
        action="store_true",
        default=False,
        dest="no_run_name")

    parser.add_option(
        "--no-symlink-dirs",
        help="Use this option to override creating default local symlinks.",
        action="store_true",
        default=False,
        dest="no_symlinks")

    return parser


@cli_function(get_option_parser)
def main(parser, opts, flow_name=None, src=None):
    if opts.no_run_name and opts.run_name:
        parser.error(
            """options --no-run-name and --run-name are mutually exclusive.
            Use one or the other""")

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

    flow_name = install_workflow(
        flow_name=opts.flow_name,
        source=opts.source,
        run_name=opts.run_name,
        no_run_name=opts.no_run_name,
        no_symlinks=opts.no_symlinks)

    for entry_point in pkg_resources.iter_entry_points(
        'cylc.post_install'
    ):
        try:
            entry_point.resolve()(
                dir_=os.getcwd(),
                opts=opts,
                dest_root=get_workflow_run_dir(flow_name)
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
