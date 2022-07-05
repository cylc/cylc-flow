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

Examples:
  # Having previously installed:
  $ cylc install myflow

  # To reinstall the latest run:
  $ cylc reinstall myflow

  # Or, to reinstall a specific run:
  $ cylc reinstall myflow/run2

  # View the changes reinstall would make:
  $ cylc reinstall myflow --dry-run
"""

from pathlib import Path
import sys
from typing import Optional, TYPE_CHECKING

from ansimarkup import parse as cparse

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

    parser.add_option(
        '--dry', '--dry-run',
        action='store_true',
        help='Show the changes reinstallation would make.'
    )

    return parser


def format_rsync_out(out):
    """Format rsync stdout for presenting to users.

    Note: Output formats of different rsync implementations may differ so keep
          this code simple and robust.

    """
    lines = []
    for line in out.splitlines():
        if line[0:4] == 'send':
            # file added or updated
            lines.append(cparse(f'<green>{line}</green>'))
        elif line[0:4] == 'del.':
            # file deleted
            lines.append(cparse(f'<red>{line}</red>'))
        elif line == 'cannot delete non-empty directory: opt':
            # These "cannot delete non-empty directory" messages can arise
            # as a result of excluding files within sub-directories.
            # This opt dir message is likely to occur when a rose-suit.conf
            # file is present.
            continue
        else:
            # other uncategorised log line
            lines.append(line)
    return lines


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

    if not opts.dry:
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

    stdout = reinstall_workflow(
        source=Path(source),
        named_run=workflow_id,
        rundir=run_dir,
        dry_run=opts.dry,
    )

    if Path(source, 'rose-suite.conf').is_file():
        print(
            cparse(
                '<blue>'
                'NOTE: Files created by Rose file installation will show as'
                ' deleted.'
                '\n      They will be re-created during the reinstall'
                ' process.'
                '</blue>',
            ),
            file=sys.stderr,
        )
    print('\n'.join(format_rsync_out(stdout)), file=sys.stderr)

    if not opts.dry:
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
