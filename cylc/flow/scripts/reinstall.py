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

  # If the workflow is running:
  $ cylc reinstall myflow  # reinstall as usual
  $ cylc reload myflow     # pick up changes in the workflow config

What reinstall does:
  Reinstall synchronises files between the workflow source and the specified
  run directory.

  Any files which have been added, updated or removed in the source directory
  will be added, updated or removed in the run directory. Cylc uses "rsync"
  to do this (run in "--debug" mode to see the exact command used).

How changes are displayed:
  Reinstall will first perform a dry run showing the files it would change.
  This is displayed in "rsync" format e.g:

    <g>send foo</g>   # this means the file "foo" would be added/updated
    <r>del. bar</r>   # this means the file "bar" would be deleted

How to prevent reinstall deleting files:
  Reinstall will delete any files which are not present in the source directory
  (i.e. if you delete a file from the source directory, a reinstall would
  remove the file from the run directory too). The "work/" and "share/"
  directory are excluded from this. These are the recommended locations for any
  files created at runtime.

  You can extend the list of "excluded" paths by creating a ".cylcignore" file.
  For example the following file would exclude "data/" and any ".csv" files
  from being overwritten by a reinstallation:

    $ cat .cylcignore
    data
    *.csv

  Note any paths listed in ".cylcignore" will not be installed by
  "cylc install" even if present in the source directory.
"""

from pathlib import Path
import sys
from typing import Optional, TYPE_CHECKING, List, Callable

from ansimarkup import parse as cparse

from cylc.flow import iter_entry_points
from cylc.flow.exceptions import (
    PluginError,
    ServiceFileError,
    WorkflowFilesError,
)
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    OptionSettings,
    Options,
    WORKFLOW_ID_ARG_DOC,
)
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.workflow_files import (
    get_workflow_source_dir,
    load_contact_file,
    reinstall_workflow,
)
from cylc.flow.terminal import cli_function, DIM, is_terminal

if TYPE_CHECKING:
    from optparse import Values

_input = input  # to enable testing


REINSTALL_CYLC_ROSE_OPTIONS = [
    OptionSettings(
        ['--clear-rose-install-options'],
        help="Clear options previously set by cylc-rose.",
        action='store_true',
        default=False,
        dest="clear_rose_install_opts",
        sources={'reinstall'}
    )
]


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
        for option in REINSTALL_CYLC_ROSE_OPTIONS:
            parser.add_option(*option.args, **option.kwargs)
    return parser


ReInstallOptions = Options(get_option_parser())


@cli_function(get_option_parser)
def main(
    _parser: COP,
    opts: 'Values',
    args: Optional[str] = None
) -> None:
    """CLI wrapper."""
    reinstall_cli(opts, args)


def reinstall_cli(
    opts: 'Values',
    args: Optional[str] = None,
) -> bool:
    """Implement cylc reinstall.

    This is the bit which contains all the CLI logic.
    """
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
    source: Path = Path(source)
    if not source.is_dir():
        raise WorkflowFilesError(
            f'Workflow source dir is not accessible: "{source}".\n'
            f'Restore the source or modify the "{source_symlink}"'
            ' symlink to continue.'
        )

    usr: str = ''
    try:
        if is_terminal():  # interactive mode - perform dry-run and prompt
            # dry-mode reinstall
            if not reinstall(
                opts,
                workflow_id,
                source,
                run_dir,
                dry_run=True,
            ):
                # no rsync output == no changes => exit
                print(cparse(
                    '<magenta>'
                    f'{workflow_id} up to date with {source}'
                    '</magenta>'
                ))
                return False

            display_rose_warning(source)
            display_cylcignore_tip()

            # prompt for permission to continue
            while usr not in ['y', 'n']:
                usr = _input(
                    cparse('<bold>Continue [y/n]: </bold>')
                ).lower()

        else:  # non interactive-mode - no dry-run, no prompt
            usr = 'y'

    except KeyboardInterrupt:
        # ensure the "reinstall canceled" message shows for ctrl+c
        usr = 'n'  # cancel the reinstall
        print()    # clear the traceback line
        return False

    if usr == 'y':
        # reinstall for real
        reinstall(opts, workflow_id, source, run_dir, dry_run=False)
        print(cparse('<green>Successfully reinstalled.</green>'))
        display_cylc_reload_tip(workflow_id)

    else:
        # no reinstall
        print(
            cparse('<magenta>Reinstall canceled, no changes made.</magenta>')
        )
        return False

    return True


def reinstall(
    opts: 'Values',
    workflow_id: str,
    src_dir: Path,
    run_dir: Path,
    dry_run: bool = False,
    write: Callable = print,
) -> bool:
    """Perform reinstallation.

    This is the purely functional bit without the CLI logic.

    Args:
        opts: CLI options.
        workflow_id: Workflow ID as a string.
        src_dir: Workflow source directory path.
        run_dir: Installed workflow run directory path.
        dry_run: If True perform a "dry run" which doesn't change anything.
        write: Used to display dry_run output.

    Returns:
        reinstall_needed - In dry_run mode returns False if rsync *would*
        update anything, else returns True.

    """
    # run pre_configure plugins
    if not dry_run:
        # don't run plugins in dry-mode
        pre_configure(opts, src_dir)

    # reinstall from src_dir (will raise WorkflowFilesError on error)
    stdout: str = reinstall_workflow(
        source=src_dir,
        named_run=workflow_id,
        rundir=run_dir,
        dry_run=dry_run,
    )

    # display changes
    if dry_run:
        if not stdout or stdout == 'send ./':
            # no rsync output == no changes => exit
            return False

        # display rsync output
        write('\n'.join(format_rsync_out(stdout)), file=sys.stderr)

    # run post_install plugins
    if not dry_run:
        # don't run plugins in dry-mode
        post_install(opts, src_dir, run_dir)

    return True


def format_rsync_out(out: str) -> List[str]:
    r"""Format rsync stdout for presenting to users.

    Note: Output formats of different rsync implementations may differ so keep
          this code simple and robust.

    Example:
        >>> format_rsync_out(
        ...     'send foo\ndel. bar\nbaz'
        ...     '\ncannot delete non-empty directory: opt'
        ... ) == [
        ...     cparse('<green>send foo</green>'),
        ...     cparse('<red>del. bar</red>'),
        ...     'baz',
        ... ]
        True

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


def pre_configure(opts: 'Values', src_dir: Path) -> None:
    """Run pre_configure plugins."""
    # don't run plugins in dry-mode
    for entry_point in iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            entry_point.resolve()(srcdir=src_dir, opts=opts)
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None


def post_install(opts: 'Values', src_dir: Path, run_dir: Path) -> None:
    """Run post_install plugins."""
    for entry_point in iter_entry_points(
        'cylc.post_install'
    ):
        try:
            entry_point.resolve()(
                srcdir=src_dir,
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


def display_rose_warning(src_dir: Path) -> None:
    """Explain why rose installed files are marked as deleted."""
    if (src_dir / 'rose-suite.conf').is_file():
        # TODO: remove this in combination with
        # https://github.com/cylc/cylc-rose/issues/149
        print(
            cparse(
                f'\n<{DIM}>'
                'NOTE: Files created by Rose file installation will show'
                ' as deleted.'
                '\n      They will be re-created during the reinstall'
                ' process.'
                f'</{DIM}>',
            ),
            file=sys.stderr,
        )


def display_cylcignore_tip():
    print(
        cparse(
            f'\n<{DIM}>TIP: You can "exclude" files/dirs to prevent'
            ' Cylc from installing or overwriting\n     them by adding'
            ' them to the .cylcignore file. See cylc reinstall --help.'
            f'</{DIM}>\n'
            '\n<bold>Reinstall would make the above changes.</bold>'
        )
    )


def display_cylc_reload_tip(workflow_id: str) -> None:
    """Recommend use of "cylc reload" if applicable.

    Uses a quick and simple way to tell if a workflow is running.

    It would be better to "ping" the workflow, however, this is sufficient
    for our purposes.
    """
    try:
        load_contact_file(workflow_id)
    except ServiceFileError:
        return
    print(cparse(
        '\n<blue>'
        f'Run "cylc reload {workflow_id}" to pick up changes.'
        '</blue>'
    ))
