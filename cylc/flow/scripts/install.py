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

"""cylc install [OPTIONS] ARGS

Install a new workflow.

The workflow can then be started, stopped, and targeted by name.

Normal installation creates a directory "~/cylc-run/WORKFLOW_NAME/", with a run
directory "~/cylc-run/WORKFLOW_NAME/run1". A "_cylc-install/source" symlink to
the source directory will be created in the WORKFLOW_NAME directory.
Any files or directories (excluding .git, .svn) from the source directory are
copied to the new run directory.
A ".service" directory will also be created and used for server authentication
files at run time.

If the argument WORKFLOW_NAME is used, Cylc will search for the workflow in the
list of directories given by "global.cylc[install]source dirs", and install the
first match. Otherwise, the workflow in the current working directory, or the
one specified by the "--directory" option, will be installed.

Workflow names can be hierarchical, corresponding to the path under ~/cylc-run.

Examples:
  # Install workflow "dogs/fido" from the first match in
  # `global.cylc[install]source dirs`, e.g. ~/cylc-src/dogs/fido/flow.cylc,
  # with run directory ~/cylc-run/dogs/fido/run1 (if "run1" already exists,
  # this will increment)
  $ cylc install dogs/fido

  # Install $PWD/flow.cylc as "rabbit", if $PWD is ~/bunny/rabbit, with
  # run directory ~/cylc-run/rabbit/run1
  $ cylc install

  # Install $PWD/flow.cylc as "rabbit", if $PWD is ~/bunny/rabbit, with
  # run directory ~/cylc-run/rabbit (note: no "run1" sub-directory)
  $ cylc install --no-run-name

  # Install $PWD/flow.cylc as "fido", regardless of what $PWD is, with
  # run directory ~/cylc-run/fido/run1
  $ cylc install --flow-name=fido

  # Install $PWD/bunny/rabbit/flow.cylc as "rabbit", with run directory
  # ~/cylc-run/rabbit/run1
  $ cylc install --directory=bunny/rabbit

  # Install $PWD/flow.cylc as "cats", if $PWD is ~/cats, overriding the
  # run1, run2, run3 etc. structure with run directory ~/cylc-run/cats/paws
  $ cylc install --run-name=paws

The same workflow can be installed with multiple names; this results in
multiple workflow run directories that link to the same workflow definition.

"""

from typing import Optional, TYPE_CHECKING, Dict, Any

from cylc.flow import iter_entry_points
from cylc.flow.exceptions import PluginError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.workflow_files import (
    install_workflow, search_install_source_dirs, parse_cli_sym_dirs
)
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    parser = COP(
        __doc__, comms=True, prep=True,
        argdoc=[('[WORKFLOW_NAME]', 'Workflow name')]
    )

    parser.add_option(
        "--flow-name",
        help="Install into ~/cylc-run/<workflow_name>/runN ",
        action="store",
        metavar="WORKFLOW_NAME",
        default=None,
        dest="workflow_name")

    parser.add_option(
        "--directory", "-C",
        help="Install the workflow found in path specfied.",
        action="store",
        metavar="PATH/TO/FLOW",
        default=None,
        dest="source")

    parser.add_option(
        "--symlink-dirs",
        help=(
            "Enter a list, in the form 'log=path/to/store, share = $...'"
            ". Use this option to override local symlinks for directories run,"
            " log, work, share, share/cycle, as configured in global.cylc. "
            "Enter an empty list \"\" to skip making localhost symlink dirs."
        ),
        action="store",
        dest="symlink_dirs"
    )

    parser.add_option(
        "--run-name",
        help="Name the run.",
        action="store",
        metavar="RUN_NAME",
        default=None,
        dest="run_name")

    parser.add_option(
        "--no-run-name",
        help="Install the workflow directly into ~/cylc-run/<workflow_name>",
        action="store_true",
        default=False,
        dest="no_run_name")

    parser.add_cylc_rose_options()

    return parser


@cli_function(get_option_parser)
def main(parser, opts, reg=None):
    install(parser, opts, reg)


def install(
    parser: COP, opts: 'Values', reg: Optional[str] = None
) -> None:
    if opts.no_run_name and opts.run_name:
        parser.error(
            "options --no-run-name and --run-name are mutually exclusive.")

    if reg is None:
        source = opts.source
    else:
        if opts.source:
            parser.error(
                "WORKFLOW_NAME and --directory are mutually exclusive.")
        source = search_install_source_dirs(reg)
    workflow_name = opts.workflow_name or reg

    for entry_point in iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            if source:
                entry_point.resolve()(srcdir=source, opts=opts)
            else:
                from pathlib import Path
                entry_point.resolve()(srcdir=Path().cwd(), opts=opts)
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None
    cli_symdirs: Optional[Dict[str, Dict[str, Any]]] = None
    if opts.symlink_dirs == '':
        cli_symdirs = {}
    elif opts.symlink_dirs:
        cli_symdirs = parse_cli_sym_dirs(opts.symlink_dirs)
    source_dir, rundir, _workflow_name = install_workflow(
        workflow_name=workflow_name,
        source=source,
        run_name=opts.run_name,
        no_run_name=opts.no_run_name,
        cli_symlink_dirs=cli_symdirs
    )

    for entry_point in iter_entry_points(
        'cylc.post_install'
    ):
        try:
            entry_point.resolve()(
                srcdir=source_dir,
                opts=opts,
                rundir=str(rundir)
            )
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.post_install',
                entry_point.name,
                exc
            ) from None
