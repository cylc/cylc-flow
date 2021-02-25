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

"""cylc reinstall [OPTIONS] ARGS

Reinstall a previously installed workflow.

Examples:
  # Having previously installed:
  $ cylc install myflow
  # To reinstall this workflow run:
  $ cylc reinstall myflow/run1

  # Having previously installed:
  $ cylc install myflow --no-run-name
  # To reinstall this workflow run:
  $ cylc reinstall myflow

  # To reinstall a workflow from within the cylc-run directory of a previously
  # installed workflow:
  $ cylc reinstall

"""


from pathlib import Path
import pkg_resources

from cylc.flow.exceptions import PluginError, WorkflowFilesError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.platforms import get_platform
from cylc.flow.suite_files import (
    get_workflow_source_dir,
    reinstall_workflow,
    SuiteFiles)
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, prep=True,
        argdoc=[("[NAMED_RUN]", "Named run. e.g. my-flow/run1")
                ])

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
        parser.add_option(
            "--clear-rose-install-options",
            help=(
                "Clear options previously set by cylc-rose."
            ),
            action='store_true',
            default=False,
            dest="clear_rose_install_opts"
        )
    except ImportError:
        pass

    return parser


@cli_function(get_option_parser)
def main(parser, opts, named_run=None):
    if not named_run:
        source, _ = get_workflow_source_dir(Path.cwd())
        if source is None:
            raise WorkflowFilesError(
                f'"{Path.cwd()}" is not a workflow run directory.')
        base_run_dir = Path(
            get_platform()['run directory'].replace('$HOME', '~')).expanduser()
        named_run = Path.cwd().relative_to(Path(base_run_dir).resolve())
    run_dir = Path(get_workflow_run_dir(named_run)).expanduser()
    if not run_dir.exists():
        raise WorkflowFilesError(
            f'\"{named_run}\" is not an installed workflow.')
    if run_dir.name in [SuiteFiles.FLOW_FILE, SuiteFiles.SUITE_RC]:
        run_dir = run_dir.parent
        named_run = named_run.rsplit('/', 1)[0]
    source, source_path = get_workflow_source_dir(run_dir)
    if not source:
        raise WorkflowFilesError(
            f'\"{named_run}\" was not installed with cylc install.')
    source = Path(source)
    if not source.exists():
        raise WorkflowFilesError(
            f'Workflow source dir is not accessible: \"{source}\".\n'
            f'Restore the source or modify the \"{source_path}\"'
            ' symlink to continue.'
        )
    for entry_point in pkg_resources.iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            entry_point.resolve()(dir_=source, opts=opts)
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None

    reinstall_workflow(
        named_run=named_run,
        rundir=run_dir,
        source=source,
        dry_run=False  # TODO: ready for dry run implementation
    )

    for entry_point in pkg_resources.iter_entry_points(
        'cylc.post_install'
    ):
        try:
            entry_point.resolve()(
                dir_=source,
                opts=opts,
                dest_root=str(run_dir)
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
