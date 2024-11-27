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
"""cylc main entry point"""

import os
import sys


def pythonpath_manip():
    """Stop PYTHONPATH contaminating the Cylc Environment

    * Remove PYTHONPATH items from sys.path to prevent PYTHONPATH
      contaminating the Cylc Environment.
    * Add items from CYLC_PYTHONPATH to sys.path.

    See Also:
        https://github.com/cylc/cylc-flow/issues/5124
    """
    if 'CYLC_PYTHONPATH' in os.environ:
        paths = [
            os.path.abspath(item)
            for item in os.environ['CYLC_PYTHONPATH'].split(os.pathsep)
        ]
        paths.extend(sys.path)
        sys.path = paths
    if 'PYTHONPATH' in os.environ:
        for item in os.environ['PYTHONPATH'].split(os.pathsep):
            abspath = os.path.abspath(item)
            if abspath in sys.path:
                sys.path.remove(abspath)


pythonpath_manip()

if sys.version_info[:2] > (3, 11):
    from importlib.metadata import (
        entry_points,
        files,
    )
else:
    # BACK COMPAT: importlib_metadata
    #   importlib.metadata was added in Python 3.8. The required interfaces
    #   were completed by 3.12. For lower versions we must use the
    #   importlib_metadata backport.
    # FROM: Python 3.7
    # TO: Python: 3.12
    from importlib_metadata import (
        entry_points,
        files,
    )

import argparse
from contextlib import contextmanager
from typing import Iterator, NoReturn, Optional, Tuple

from ansimarkup import parse as cparse

from cylc.flow import __version__, iter_entry_points
from cylc.flow.option_parsers import (
    format_help_headings,
    format_shell_examples,
)
from cylc.flow.scripts.common import cylc_header


def get_version(long=False):
    """Return version string, and (if long is True) install location.

    The install location returned is the top directory of the virtual
    environment, obtained from the Python executable path. (cylc-flow file
    locations are buried deep in the library and don't always give the right
    result, e.g. if installed with `pip install -e .`).
    """
    from pathlib import Path
    version = f"{__version__}"
    if long:
        version += f" ({Path(sys.argv[0])})"
    return version


USAGE = f"""{cylc_header()}
Cylc ("silk") efficiently manages distributed cycling workflows.
Cylc is Open Source software (GPL-3.0): see "cylc help license".

Version:
  $ cylc version --long
  {get_version(True)}

Quick Start:
  $ cylc install <path>       # install a workflow
  $ cylc play <workflow_id>   # run or resume a workflow
  $ cylc stop <workflow_id>   # stop a workflow
  $ cylc clean <workflow_id>  # delete an installed workflow
  $ cylc gui                  # start the in-browser web UI
  $ cylc tui <workflow_id>    # start the in-terminal UI

  $ cylc help all             # see all cylc commands
  $ cylc <command> --help     # specific command help

Cylc IDs:
  Workflows and tasks are identified by IDs of the form:
    workflow//cycle/task

  You can split an ID at the // so following two IDs are equivalent:
    workflow//cycle1 workflow//cycle2
    workflow// //cycle1 //cycle2

  IDs can be written as globs:
    *//                 # All workflows
    workflow//*         # All cycle points in "workflow"
    workflow//cycle/*   # All tasks in cycle point "cycle" of "workflow"

  $ cylc help id        # More information on IDs

Cylc commands can be abbreviated:
  $ cylc trigger workflow//cycle/task    # trigger task in workflow
  $ cylc trig workflow//cycle/task       # trigger task in workflow
  $ cylc t                               # error: trigger or tui?
"""

ID_HELP = '''
Workflow IDs:
    Every Installed Cylc workflow has an ID.

    For example if we install a workflow like so:
      $ cylc install --workflow-name=foo

    We will end up with a workflow with the ID "foo/run1".

    This ID can be used to interact with the workflow:
      $ cylc play foo/run1
      $ cylc pause foo/run1
      $ cylc stop foo/run1

    In the case of numbered runs (e.g. "run1", "run2", ...) you can omit
    the run number, Cylc will infer latest run.
      $ cylc play foo
      $ cylc pause foo
      $ cylc stop foo

    Workflows can be installed hierarchically:
      $ cylc install --workflow-name=foo/bar/baz

      # play the workflow with the ID "foo/bar/baz"
      $ cylc play foo/bar/baz

    The full format of a workflow ID is:
      ~user/workflow-id

    You can omit the user name when working on your own workflows.

Cycle / Family / Task / Job IDs:
    Just as workflows have IDs, the things within workflows have IDs too.
    These IDs take the format:
      cycle/task_or_family/job

    Examples:
      1      # The cycle point "1"
      1/a    # The task "a" in cycle point "1"
      1/a/1  # The first job of the task "a" in the cycle point "1".

Full ID
    We join the workflow and cycle/task/job IDs together using //:
      workflow//cycle/task/job

    Examples:
      w//         # The workflow "w"
      w//1        # The cycle "1" in the workflow "w"
      w//1/a      # The task "a" in the cycle "1" in the workflow "w"
      w//1/a/1    # The first job of w//1/a/1
      ~alice/test # The workflow "test" installed under the user
                  # account "alice"

Patterns
    Patterns can be used in Cylc IDs:
      *       # Matches everything.
      ?       # Matches any single character.
      [seq]   # Matches any character in "seq".
      [!seq]  # Matches any character not in "seq".

    Examples:
      *                      # All workflows
      test*                  # All workflows starting "test".
      test/*                 # All workflows starting "test/".
      workflow//*            # All cycles in workflow
      workflow//cycle/*      # All tasks in workflow//cycle
      workflow//cycle/task/* # All jobs in workflow//cycle/job

    Warning:
      Remember to write IDs inside single quotes when using them on the
      command line otherwise your shell may expand them.

Filters
    Filters allow you to filter for specific states.

    Filters are prefixed by a colon (:).

    Examples:
      *:running                       # All running workflows
      workflow//*:running             # All running cycles in workflow
      workflow//cycle/*:running       # All running tasks in workflow//cycle
      workflow//cycle/task/*:running  # All running jobs in
                                      # workflow//cycle/task
'''


# because this command is not served from behind cli_function like the
# other cylc commands we have to manually patch in colour support
USAGE = cparse(format_help_headings(format_shell_examples(USAGE)))

# all sub-commands
# {name: entry_point}
COMMANDS: dict = {
    entry_point.name: entry_point
    for entry_point in iter_entry_points('cylc.command')
}


# aliases for sub-commands
# {alias_name: command_name}
ALIASES = {
    'bcast': 'broadcast',
    'compare': 'diff',
    'cyclepoint': 'cycle-point',
    'cycletime': 'cycle-point',
    'datetime': 'cycle-point',
    'external-trigger': 'ext-trigger',
    'get-contact': 'get-workflow-contact',
    'get-cylc-version': 'get-workflow-version',
    'log': 'cat-log',
    'ls': 'list',
    'shutdown': 'stop',
    'task-message': 'message',
    'unhold': 'release',
    'validate-install-play': 'vip',
    'validate-reinstall': 'vr',
}


# aliases for sub-commands which no longer exist
# {alias_name: message_to_user}
# fmt: off
DEAD_ENDS = {
    'check-software':
        'use standard tools to inspect the environment'
        ' e.g. https://pypi.org/project/pipdeptree/',
    'checkpoint':
        'DB checkpoints have been removed. You can now "rewind" a'
        ' workflow by triggering the flow anywhere in the graph.',
    'conditions':
        'cylc conditions has been replaced by cylc help license',
    'documentation':
        'Cylc documentation is now at http://cylc.org',
    'edit':
        'Command removed, please edit the workflow in source directory',
    'get-directory':
        'cylc get-directory has been removed.',
    'get-config':
        'cylc get-config has been replaced by cylc config',
    'get-site-config':
        'cylc get-site-config has been replaced by cylc config',
    'get-suite-config':
        'cylc get-suite-config has been replaced by cylc config',
    'get-global-config':
        'cylc get-global-config has been replaced by cylc config',
    'graph-diff':
        'cylc graph-diff has been removed,'
        ' use cylc graph <flow1> --diff <flow2>',
    'gscan':
        'cylc gscan has been removed, use the web UI',
    'insert':
        'Insertion is no longer required, `cylc set` and `cylc trigger`'
        ' will insert tasks automatically.',
    'jobscript':
        'cylc jobscript has been removed',
    'nudge':
        'cylc nudge has been removed',
    'print':
        'cylc print has been removed; use `cylc scan --states=all`',
    'register':
        'cylc register has been removed; use cylc install or cylc play',
    'reset':
        'cylc reset has been replaced by cylc set',
    'set-outputs':
        'cylc set-outputs (cylc 8.0-8.2) has been replaced by cylc set',
    'restart':
        'cylc run & cylc restart have been replaced by cylc play',
    'review':
        'cylc review has been removed; the latest Cylc 7 version is forward'
        ' compatible with Cylc 8.',
    'suite-state':
        'cylc suite-state has been replaced by cylc workflow-state',
    'run':
        'cylc run & cylc restart have been replaced by cylc play',
    'search':
        'cylc search has been removed; please use `grep` or a text editor',
    'spawn':
        'cylc spawn has been removed; spawning is now performed automatically',
    'submit':
        'cylc submit has been removed',
    'start':
        'cylc start & cylc restart have been replaced by cylc play',
    'set-verbosity':
        'cylc set-verbosity has been replaced by cylc verbosity',
    'warranty':
        'cylc warranty has been replaced by cylc help license',
}
# fmt: on


def execute_cmd(cmd: str, *args: str) -> NoReturn:
    """Execute a sub-command.

    Args:
        cmd: The name of the command.
        args: Command line arguments to pass to that command.

    """
    entry_point = COMMANDS[cmd]
    try:
        entry_point.load()(*args)
    except ModuleNotFoundError as exc:
        msg = handle_missing_dependency(entry_point, exc)
        print(msg, file=sys.stderr)
        sys.exit(1)
    sys.exit()


def match_command(command):
    """Permit abbreviated commands (e.g. tri -> trigger).

    Args:
        command (string):
            The input string to match.

    Returns:
        string - The matched command.

    Exits:
        1:
            If the number of command matches != 1

    """
    possible_cmds = {
        *{
            # search commands
            cmd
            for cmd in COMMANDS
            if cmd.startswith(command)
        },
    }
    if len(possible_cmds) == 0:
        print(
            f"cylc {command}: unknown utility. Abort.\n"
            'Type "cylc help all" for a list of utilities.',
            file=sys.stderr
        )
        sys.exit(1)
    elif len(possible_cmds) > 1:
        print(
            "cylc {}: is ambiguous for:\n{}".format(
                command,
                "\n".join(
                    [
                        f"    cylc {cmd}"
                        for cmd in sorted(possible_cmds)
                    ]
                ),
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        command = possible_cmds.pop()
    return command


def parse_docstring(docstring):
    """Extract the description and usage lines from a sub-command docstring.

    Args:
        docstring (str):
            Multiline string i.e. __doc__

    Returns:
        tuple - (usage, description)

    """
    lines = [
        line
        for line in docstring.splitlines()
        if line
    ]
    usage = None
    desc = None
    if len(lines) > 0:
        usage = lines[0]
    if len(lines) > 1:
        desc = lines[1]
    return (usage, desc)


def iter_commands() -> Iterator[Tuple[str, Optional[str], Optional[str]]]:
    """Yield all Cylc sub-commands that are available.

    Skips sub-commands that require missing optional dependencies.

    Yields:
        (command, description, usage)

    """
    for cmd, entry_point in sorted(COMMANDS.items()):
        try:
            module = __import__(entry_point.module, fromlist=[''])
        except ModuleNotFoundError as exc:
            handle_missing_dependency(entry_point, exc)
            continue
        if getattr(module, 'INTERNAL', False):
            # do not list internal commands
            continue
        usage, desc = parse_docstring(module.__doc__)
        yield (cmd, desc, usage)


def print_id_help():
    print(ID_HELP)


def print_license() -> None:
    for file in files('cylc-flow') or []:
        if file.name == 'COPYING':
            print(file.read_text())
            return


def print_command_list(commands=None, indent=0):
    """Print list of Cylc commands.

    Args:
        commands (list):
            List of commands to display.
        indent (int):
            Number of spaces to put at the start of each line.

    """
    from cylc.flow.terminal import print_contents
    contents = [
        (cmd, desc)
        for cmd, desc, _, in iter_commands()
        if not commands
        or cmd in commands
    ]
    print_contents(contents, indent=indent, char=cparse('<dim>.</dim>'))


def cli_help():
    """Display the main Cylc help page."""
    # add a splash of colour
    # we need to do this explicitly as this command is not behind cli_function
    # (assume the cylc help is only ever requested interactively in a
    # modern terminal)
    from colorama import init as color_init
    color_init(autoreset=True, strip=False)
    print(USAGE)
    sys.exit(0)


def cli_version(long_fmt=False):
    """Wrapper for get_version."""
    print(get_version(long_fmt))
    if long_fmt:
        print(cparse(list_plugins()))
    sys.exit(0)


def list_plugins():
    from cylc.flow.terminal import DIM, format_grid
    # go through all Cylc entry points
    _dists = set()
    __entry_points = {}
    for entry_point in entry_points():
        if (
            # all Cylc entry points are under the "cylc" namespace
            entry_point.group.startswith('cylc.')
            # don't list cylc-flow entry-points (i.e. built-ins)
            and not entry_point.value.startswith('cylc.flow')
        ):
            _dists.add(entry_point.dist)
            __entry_points.setdefault(
                entry_point.group,
                [],
            ).append(entry_point)

    # list all the distriutions which provide Cylc entry points
    _plugins = []
    for dist in _dists:
        _plugins.append((
            '',
            f'<light-blue>{dist.name}</light-blue>',
            dist.version,
            f'<{DIM}>{dist.locate_file("__init__.py").parent}</{DIM}>',
        ))

    # list all of the entry points by "group" (e.g. "cylc.command")
    _entry_points = []
    for group, points in sorted(__entry_points.items()):
        _entry_points.append((f'  {group}:', '', ''))
        for entry_point in points:
            _entry_points.append((
                f'    {entry_point.name}',
                f'<light-blue>{entry_point.dist.name}</light-blue>',
                f'<{DIM}>{entry_point.value}</{DIM}>',
            ))

    return '\n'.join((
        '\n<bold>Plugins:</bold>',
        *format_grid(_plugins),
        '\n<bold>Entry Points:</bold>',
        *format_grid(
            _entry_points
        ),
    ))


@contextmanager
def pycoverage(cmd_args):  # pragma: no cover
    """Capture code coverage if configured to do so.

    This requires Cylc to be installed in editable mode
    (i.e. `pip install -e`) in order to access the coverage configuration
    file, etc.

    $ pip install -e /cylc/working/directory

    Set the CYLC_COVERAGE env var as appropriate before running tests

    $ export CYLC_COVERAGE=1

    Coverage files will be written out to the working copy irrespective
    of where in the filesystem the `cylc` command was run.

    $ cd /cylc/working/directory
    $ coverage combine
    $ coverage report

    For remote tasks the coverage files will be written to the cylc
    working directory on the remote so you will have to scp them back
    to your local working directory before running coverage combine:

    $ cd /cylc/working/directory
    $ ssh remote-host cd /cylc/remote/working/directory && coverage combine
    $ scp \
    >     remote-host/cylc/remote/working/directory/.coverage \
    >    .coverage.remote-host.12345.12345
    $ coverage combine
    $ coverage report

    Environment Variables:
        CYLC_COVERAGE:
            '0'
                Do nothing / run as normal.
            '1'
                Collect coverage data.
            '2'
                Collect coverage data and log every command for which
                coverage data was successfully recorded to
                a .coverage_commands_captured file in the Cylc
                working directory.

    """
    cylc_coverage = os.environ.get('CYLC_COVERAGE')
    if cylc_coverage not in ('1', '2'):
        yield
        return

    # import here to avoid unnecessary imports when not running coverage
    import cylc.flow
    import coverage
    from pathlib import Path

    # the cylc working directory
    cylc_wc = Path(cylc.flow.__file__).parents[2]

    # initiate coverage
    try:
        cov = coverage.Coverage(
            # NOTE: coverage paths are all relative so we must hack them here
            # to absolute values, otherwise when `cylc` scripts are run
            # elsewhere on the filesystem they will fail to capture coverage
            # data and will dump empty coverage files where they run.
            config_file=str(cylc_wc / '.coveragerc'),
            data_file=str(cylc_wc / '.coverage'),
            source=[str(cylc_wc / 'cylc')]
        )
    except coverage.misc.CoverageException:
        raise Exception(
            # make sure this exception is visible in the traceback
            '\n\n*****************************\n\n'
            'Could not initiate coverage, likely because Cylc was not '
            'installed in editable mode.'
            '\n\n*****************************\n\n'
        )

    # start the coverage running
    cov.start()
    try:
        # yield control back to cylc, return once the command exits
        yield
    finally:
        # stop the coverage and save the data
        cov.stop()
        cov.save()
        if cylc_coverage == '2':
            with open(cylc_wc / '.coverage_commands_captured', 'a+') as ccc:
                ccc.write(
                    '$ cylc ' + (' '.join(cmd_args) + '\n'),
                )


def get_arg_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '--help', '-h',
        action='store_true',
        default=False,
        dest='help_'
    )
    parser.add_argument(
        '--version', '-V',
        action='store_true',
        default=False,
        dest='version'
    )
    return parser


def main():
    opts, cmd_args = get_arg_parser().parse_known_args()
    with pycoverage(cmd_args):
        if not cmd_args:
            if opts.version:
                cli_version()
            else:
                cli_help()
        else:
            cmd_args = list(cmd_args)
            command = cmd_args.pop(0)

            if command == "version":
                cli_version("--long" in cmd_args)

            if command == "help":
                opts.help_ = True
                if not len(cmd_args):
                    cli_help()
                elif cmd_args == ['all']:
                    print_command_list()
                    sys.exit(0)
                elif cmd_args == ['id']:
                    print_id_help()
                    sys.exit(0)
                if cmd_args in (['license'], ['licence']):
                    print_license()
                    sys.exit(0)
                else:
                    command = cmd_args.pop(0)

            # this is an alias to a command
            if command in ALIASES:
                command = ALIASES.get(command)

            if command in DEAD_ENDS:
                # this command has been removed but not aliased
                # display a helpful message and move on#
                print(
                    cparse(
                        f'<red>{DEAD_ENDS[command]}</red>'
                    )
                )
                sys.exit(42)

            if command not in COMMANDS:
                # check if this is a command abbreviation or exit
                command = match_command(command)
            if opts.help_:
                execute_cmd(command, *cmd_args, "--help")
            else:
                if opts.version:
                    cmd_args.append("--version")
                execute_cmd(command, *cmd_args)


def handle_missing_dependency(
    entry_point,
    err: ModuleNotFoundError
) -> str:
    """Return a suitable error message for a missing optional dependency.

    Args:
        entry_point: The entry point that was attempted to load but caused
            a ModuleNotFoundError.
        err: The ModuleNotFoundError that was caught.

    Re-raises the given ModuleNotFoundError if it is unexpected.
    """
    msg = f'"cylc {entry_point.name}" requires "{entry_point.dist.name}'
    if entry_point.extras:
        msg += f'[{",".join(entry_point.extras)}]'
    msg += f'"\n\n{err.__class__.__name__}: {err}'
    return msg
