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

The workflow can then be started, stopped, and targeted by name.

Normal installation creates a directory "~/cylc-run/REG/", with a run
directory "~/cylc-run/REG/run1" containing a "_cylc-install/source" symlink to
the source directory.
Any files or directories (excluding .git, .svn) from the source directory are
copied to the new run directory.
A ".service" directory will also be created and used for server authentication
files at run time.

If the argument REG is used, Cylc will search for the workflow in the list of
directories given by "global.cylc[install]source dirs", and install the first
match. Otherwise, the workflow in the current working directory, or the one
specified by the "--directory" option, will be installed.

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

  # Install $PWD/bunny/rabbit/flow.cylc as "bunny/rabbit", with run directory
  # ~/cylc-run/bunny/rabbit/run1
  $ cylc install --directory=bunny/rabbit

  # Install $PWD/cats/flow.cylc as "cats", overriding the run1, run2, run3 etc
  # structure with run directory ~/cylc-run/cats/paws
  $ cylc install --run-name=paws

The same workflow can be installed with multiple names; this results in
multiple workflow run directories that link to the same suite definition.

"""


import pkg_resources
from typing import Optional, TYPE_CHECKING

from cylc.flow.exceptions import PluginError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.suite_files import install_workflow, search_install_source_dirs
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from cylc.flow.option_parsers import Options


def get_option_parser():
    parser = COP(
        __doc__, comms=True, prep=True,
        argdoc=[("[REG]", "Workflow name")]
    )

    parser.add_option(
        "--flow-name",
        help="Install into ~/cylc-run/<flow_name>/runN ",
        action="store",
        metavar="FLOW_NAME",
        default=None,
        dest="flow_name")

    parser.add_option(
        "--directory", "-C",
        help="Install the workflow found in path specfied.",
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
        help="Install the workflow directly into ~/cylc-run/<flow_name>",
        action="store_true",
        default=False,
        dest="no_run_name")

    parser.add_option(
        "--no-symlink-dirs",
        help="Use this option to override creating default local symlinks.",
        action="store_true",
        default=False,
        dest="no_symlinks")

    # If cylc-rose plugin is available ad the --option/-O config
    try:
        __import__('cylc.rose')
        parser.add_option(
            "--opt-conf-key", "-O",
            help=(
                "Use optional Rose Config Setting"
                "(If Cylc-Rose is installed)"
            ),
            action="append",
            default=[],
            dest="opt_conf_keys"
        )
        parser.add_option(
            "--define", '-D',
            help=(
                "Each of these overrides the `[SECTION]KEY` setting in a "
                "`rose-suite.conf` file. "
                "Can be used to disable a setting using the syntax "
                "`--define=[SECTION]!KEY` or even `--define=[!SECTION]`."
            ),
            action="append",
            default=[],
            dest="defines"
        )
        parser.add_option(
            "--define-suite", "--define-flow", '-S',
            help=(
                "As `--define`, but with an implicit `[SECTION]` for "
                "workflow variables."
            ),
            action="append",
            default=[],
            dest="define_suites"
        )
    except ImportError:
        pass

    return parser


@cli_function(get_option_parser)
def main(parser, opts, reg=None):
    install(parser, opts, reg)


def install(
    parser: COP, opts: 'Options', reg: Optional[str] = None
) -> None:
    if opts.no_run_name and opts.run_name:
        parser.error(
            "options --no-run-name and --run-name are mutually exclusive.")

    if reg is None:
        source = opts.source
    else:
        if opts.source:
            parser.error("REG and --directory are mutually exclusive.")
        source = search_install_source_dirs(reg)
    flow_name = opts.flow_name or reg

    for entry_point in pkg_resources.iter_entry_points(
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

    source_dir, rundir, _flow_name = install_workflow(
        flow_name=flow_name,
        source=source,
        run_name=opts.run_name,
        no_run_name=opts.no_run_name,
        no_symlinks=opts.no_symlinks
    )

    for entry_point in pkg_resources.iter_entry_points(
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


if __name__ == "__main__":
    main()
