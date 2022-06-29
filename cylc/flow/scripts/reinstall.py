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

"""cylc reinstall [OPTIONS] ARGS

Reinstall a previously installed workflow.

WARNING: this uninstalls previously-installed files that have since been
removed from the source directory, by detecting files outside of the standard
run sub-directory locations (share, work, log) that are not present in the
source directory. If your workflow tasks write to the top level run directory,
use the --no-delete option or (preferably) configure your .cylcignore file
appropriately, to protect these files from deletion.

Examples:
  # Having previously installed:
  $ cylc install myflow
  # To reinstall the latest run:
  $ cylc reinstall myflow
  # Or, to reinstall a specific run:
  $ cylc reinstall myflow/run2

  # Having previously installed:
  $ cylc install myflow --no-run-name
  # To reinstall this workflow run:
  $ cylc reinstall myflow
"""

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from cylc.flow import iter_entry_points
from cylc.flow.exceptions import PluginError, WorkflowFilesError
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.workflow_files import (
    get_workflow_source_dir,
    reinstall_workflow,
)
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser() -> COP:
    parser = COP(
        __doc__, comms=True, argdoc=[WORKFLOW_ID_ARG_DOC]
    )

    parser.add_option(
        "--no-delete", "-n",
        help=(
            "Do not delete files outside of the standard run sub-directories"
            " (work, share, etc.) that are not present in the source"
            " directory. NOTE: we recommend use of a .cylcignore file in the"
            " source directory rather than this option, because that does"
            " not prevent removal of previously-installed files that are"
            " no longer needed."
        ),
        action='store_true',
        default=False,
        dest="no_delete"
    )

    parser.add_cylc_rose_options()
    try:
        # If cylc-rose plugin is available
        __import__('cylc.rose')
    except ImportError:
        pass
    else:
        parser.add_option(
            "--clear-rose-install-options",
            help="Clear options previously set by cylc-rose.",
            action='store_true',
            default=False,
            dest="clear_rose_install_opts"
        )

    return parser


@cli_function(get_option_parser)
def main(
    parser: COP,
    opts: 'Values',
    args: Optional[str] = None
) -> None:
    run_dir: Optional[Path]
    workflow_id: str
    workflow_id, *_ = parse_id(
        args,
        constraint='workflows',
    )
    run_dir = Path(get_workflow_run_dir(workflow_id))
    if not run_dir.is_dir():
        raise WorkflowFilesError(
            f'"{workflow_id}" is not an installed workflow.')
    source, source_symlink = get_workflow_source_dir(run_dir)
    if not source:
        raise WorkflowFilesError(
            f'"{workflow_id}" was not installed with cylc install.')
    if not Path(source).is_dir():
        raise WorkflowFilesError(
            f'Workflow source dir is not accessible: "{source}".\n'
            f'Restore the source or modify the "{source_symlink}"'
            ' symlink to continue.'
        )
    for entry_point in iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            entry_point.resolve()(srcdir=source, opts=opts)
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None

    reinstall_workflow(
        source=Path(source),
        named_run=workflow_id,
        rundir=run_dir,
        delete=not opts.no_delete,
        dry_run=False  # TODO: ready for dry run implementation
    )

    for entry_point in iter_entry_points(
        'cylc.post_install'
    ):
        try:
            entry_point.resolve()(
                srcdir=source,
                opts=opts,
                rundir=str(run_dir)
            )
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.post_install',
                entry_point.name,
                exc
            ) from None
