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

import argparse
from contextlib import contextmanager
import os
import sys
from pathlib import Path

from ansimarkup import parse as cparse
from colorama import init as color_init
import pkg_resources

from cylc.flow import __version__, iter_entry_points
from cylc.flow.option_parsers import format_shell_examples
from cylc.flow.scripts import cylc_header
from cylc.flow.terminal import print_contents


def get_version(long=False):
    """Return version string, and (if long is True) install location.

    The install location returned is the top directory of the virtual
    environment, obtained from the Python executable path. (cylc-flow file
    locations are buried deep in the library and don't always give the right
    result, e.g. if installed with `pip install -e .`).
    """
    version = f"{__version__}"
    if long:
        version += f" ({Path(sys.executable).parent.parent})"
    return version


USAGE = f"""{cylc_header()}
Cylc ("silk") orchestrates complex cycling (and non-cycling) workflows.

Version:
  $ cylc version --long           # print cylc-flow version and install path
  {get_version(True)}

Usage:
  $ cylc help all                 # list all commands
  $ cylc validate FLOW            # validate a workflow configuration
  $ cylc play FLOW                # run/resume a workflow
  $ cylc scan                     # list all running workflows (by default)
  $ cylc tui FLOW                 # view a running workflow in the terminal
  $ cylc stop FLOW                # stop a running workflow

Command Abbreviation:
  # Commands can be abbreviated as long as there is no ambiguity in
  # the abbreviated command:
  $ cylc trigger WORKFLOW TASK    # trigger TASK in WORKFLOW
  $ cylc trig WORKFLOW TASK       # ditto
  $ cylc tr WORKFLOW TASK         # ditto
  $ cylc t                        # Error: ambiguous command

Task Identification:
  Tasks are identified by NAME.CYCLE_POINT where POINT is either a
  date-time or an integer.

  Date-time cycle points are in an ISO 8601 date-time format, typically
  CCYYMMDDThhmm followed by a time zone - e.g. 20101225T0600Z.

  Integer cycle points (including those for non-cycling workflows) are integers
  - just '1' for non-cycling workflows.
"""

# because this command is not served from behind cli_function like the
# other cylc commands we have to manually patch in colour support
USAGE = format_shell_examples(USAGE)
USAGE = cparse(USAGE)

# all sub-commands
# {name: entry_point}
COMMANDS: dict = {
    entry_point.name: entry_point
    for entry_point
    in iter_entry_points('cylc.command')
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
    'unhold': 'release'
}


# aliases for sub-commands which no longer exist
# {alias_name: message_to_user}
# fmt: off
DEAD_ENDS = {
    'check-software':
        'use standard tools to inspect the environment'
        ' e.g. https://pypi.org/project/pipdeptree/',
    'documentation':
        'Cylc documentation is now at http://cylc.org',
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
        'inserting tasks is now done automatically',
    'jobscript':
        'cylc jobscript has been removed',
    'register':
        'cylc register has been removed; use cylc install or cylc play',
    'reset':
        'cylc reset has been replaced by cylc set-outputs',
    'restart':
        'cylc run & cylc restart have been replaced by cylc play',
    'suite-state':
        'cylc suite-state has been replaced by cylc workflow-state',
    'run':
        'cylc run & cylc restart have been replaced by cylc play',
    'submit':
        'cylc submit has been removed',
    'start':
        'cylc start & cylc restart have been replaced by cylc play'
}
# fmt: on


def execute_cmd(cmd, *args):
    """Execute a sub-command.

    Args:
        cmd (str):
            The name of the command.
        args (list):
            List of command line arguments to pass to that command.

    """
    COMMANDS[cmd].resolve()(*args)
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
        *{
            # search aliases
            cmd
            for alias, cmd in ALIASES.items()
            if alias.startswith(command)
        }
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


def iter_commands():
    """Yield all Cylc sub-commands.

    Yields:
        tuple - (command, description, usage)

    """
    for cmd, obj in sorted(COMMANDS.items()):
        if cmd == 'cylc':
            # don't include this command in the listing
            continue
        if not obj:
            raise ValueError(f'Unrecognised command "{cmd}"')
        # python command
        module = __import__(obj.module_name, fromlist=[''])
        if getattr(module, 'INTERNAL', False):
            # do not list internal commands
            continue
        usage, desc = parse_docstring(module.__doc__)
        yield (cmd, desc, usage)


def print_command_list(commands=None, indent=0):
    """Print list of Cylc commands.

    Args:
        commands (list):
            List of commands to display.
        indent (int):
            Number of spaces to put at the start of each line.

    """
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
    color_init(autoreset=True, strip=False)
    print(USAGE)
    print('Selected Sub-Commands:')
    print_command_list(
        # print a short list of the main cylc commands
        commands=[
            'hold',
            'kill',
            'pause',
            'play',
            'release',
            'scan',
            'stop',
            'trigger',
            'tui',
            'validate'
        ],
        indent=2
    )
    print('\nTo see all commands run: cylc help all')
    sys.exit(0)


def cli_version(long_fmt=False):
    """Wrapper for get_version."""
    print(get_version(long_fmt))
    if long_fmt:
        print(list_plugins())
    sys.exit(0)


def list_plugins():
    entry_point_names = [
        entry_point_name
        for entry_point_name
        in pkg_resources.get_entry_map('cylc-flow').keys()
        if entry_point_name.startswith('cylc.')
    ]

    entry_point_groups = {
        entry_point_name: [
            entry_point
            for entry_point
            in iter_entry_points(entry_point_name)
            if not entry_point.module_name.startswith('cylc.flow')
        ]
        for entry_point_name in entry_point_names
    }

    dists = {
        entry_point.dist
        for entry_points in entry_point_groups.values()
        for entry_point in entry_points
    }

    lines = []
    if dists:
        lines.append('\nPlugins:')
        maxlen1 = max(len(dist.project_name) for dist in dists) + 2
        maxlen2 = max(len(dist.version) for dist in dists) + 2
        for dist in dists:
            lines.append(
                f'  {dist.project_name.ljust(maxlen1)}'
                f' {dist.version.ljust(maxlen2)}'
                f' {dist.module_path}'
            )

        lines.append('\nEntry Points:')
        for entry_point_name, entry_points in entry_point_groups.items():
            if entry_points:
                lines.append(f'  {entry_point_name}:')
                for entry_point in entry_points:
                    lines.append(f'    {entry_point}')

    return '\n'.join(lines)


@contextmanager
def pycoverage(cmd_args):
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
                else:
                    command = cmd_args.pop(0)

            if command in ALIASES:
                # this is an alias to a command
                command = ALIASES[command]

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
                execute_cmd(command, "--help")
            else:
                if opts.version:
                    cmd_args.append("--version")
                execute_cmd(command, *cmd_args)
