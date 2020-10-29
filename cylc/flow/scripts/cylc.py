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
"""cylc main entry point"""

import os
import sys

from ansimarkup import parse as cparse
import click
from colorama import init as color_init
import pkg_resources

from cylc.flow import __version__
from cylc.flow.scripts import cylc_header
from cylc.flow.terminal import (
    centered,
    format_shell_examples,
    print_contents
)


DESC = '''
Cylc ("silk") is a workflow engine for orchestrating complex *suites* of
inter-dependent distributed cycling (repeating) tasks, as well as ordinary
non-cycling workflows.
'''

USAGE = f"""{cylc_header()}
{centered(DESC)}

Usage:
  $ cylc help all                 # list all commands
  $ cylc validate FLOW            # validate a workflow definition
  $ cylc run FLOW                 # run a workflow
  $ cylc tui FLOW                 # view a running workflow in the terminal
  $ cylc stop FLOW                # stop a running workflow

Command Abbreviation:
  # Commands can be abbreviated as long as there is no ambiguity in
  # the abbreviated command:
  $ cylc trigger SUITE TASK       # trigger TASK in SUITE
  $ cylc trig SUITE TASK          # ditto
  $ cylc tr SUITE TASK            # ditto
  $ cylc t                        # Error: ambiguous command

Task Identification:
  Tasks are identified by NAME.CYCLE_POINT where POINT is either a
  date-time or an integer.

  Date-time cycle points are in an ISO 8601 date-time format, typically
  CCYYMMDDThhmm followed by a time zone - e.g. 20101225T0600Z.

  Integer cycle points (including those for one-off suites) are integers
  - just '1' for one-off suites.
"""

# because this command is not served from behind cli_function like the
# other cylc commands we have to manually patch in colour support
USAGE = format_shell_examples(USAGE)
USAGE = cparse(USAGE)

# bash sub-commands
# {name: (description, usage)}
bash_commands = {
    'graph-diff': (
        'Compare the graphs of two workflows in text format.',
        'cylc graph-diff [OPTIONS] SUITE1 SUITE2 -- '
        '[GRAPH_OPTIONS_ARGS]'
    )
}

# all sub-commands
# {name: entry_point}
commands = {
    # TODO: remove the cylc-flow constraint
    **pkg_resources.get_entry_map("cylc-flow").get("cylc.command"),
    **{
        cmd: None
        for cmd in bash_commands
    }
}


# aliases for sub-commands
# {alias_name: command_name}
ALIASES = {
    'bcast': 'broadcast',
    'compare': 'diff',
    'cyclepoint': 'cycle_point',
    'cycletime': 'cycle_point',
    'datetime': 'cycle_point',
    'external-trigger': 'ext_trigger',
    'get-config': 'get_suite_config',
    'get-contact': 'get_suite_contact',
    'get-cylc-version': 'get_suite_version',
    'get-global-config': 'get_site_config',
    'grep': 'search',
    'log': 'cat_log',
    'ls': 'list',
    'shutdown': 'stop',
    'start': 'run',
    'task-message': 'message',
    'unhold': 'release'
}


def execute_bash(cmd, *args):
    """Execute Bash sub-command.

    Note:
        Replaces the current process with that of the sub-command.

    """
    cmd = f'cylc-{cmd}'
    try:
        os.execvp(cmd, [cmd] + list(args))  # nosec
    except OSError as exc:
        if exc.filename is None:
            exc.filename = cmd
        raise click.ClickException(exc)


def execute_python(cmd, *args):
    """Execute a Python sub-command.

    Note:
        Imports the function and calls it in the current Python session.

    """
    commands[cmd].resolve()(*args)


def execute_cmd(cmd, *args):
    """Execute a sub-command.

    Args:
        cmd (str):
            The name of the command.
        args (list):
            List of command line arguments to pass to that command.

    """
    if cmd in bash_commands:
        execute_bash(cmd, *args)
    else:
        execute_python(cmd, *args)
    sys.exit()


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
    for cmd, obj in sorted(commands.items()):
        if cmd == 'cylc':
            # don't include this command in the listing
            continue
        if obj:
            # python command
            module = __import__(obj.module_name, fromlist=[''])
            if getattr(module, 'INTERNAL', False):
                # do not list internal commands
                continue
            usage, desc = parse_docstring(module.__doc__)
            yield (cmd, desc, usage)
        elif cmd in bash_commands:
            # bash command
            desc, usage = bash_commands[cmd]
            yield (cmd, desc, usage)
        else:
            raise ValueError(f'Unrecognised command "{cmd}"')


def print_command_list(commands=None):
    """Print list of Cylc commands."""
    contents = [
        (cmd, desc)
        for cmd, desc, _, in iter_commands()
        if not commands
        or cmd in commands
    ]
    print_contents(contents, indent=2)


def cli_help():
    """Display the main Cylc help page."""
    # add a splash of colour
    # we need to do this explicitly as this command is not behind cli_function
    # (assume the cylc help is only ever requested interactively in a
    # modern terminal)
    color_init(autoreset=True, strip=False)
    print(USAGE)
    print('Selected Sub-Commands:')
    print_command_list(commands=['validate', 'run', 'restart', 'stop', 'tui'])
    print('\nTo see all commands run: cylc help all')
    sys.exit(0)


def cli_version():
    """Display the Cylc Flow version."""
    click.echo(__version__)
    sys.exit(0)


@click.command(context_settings={'ignore_unknown_options': True})
@click.option("--help", "-h", "help_", is_flag=True, is_eager=True)
@click.option("--version", "-V", is_flag=True, is_eager=True)
@click.argument("cmd-args", nargs=-1)
def main(cmd_args, version, help_):
    if not cmd_args:
        if version:
            cli_version()
        else:
            cli_help()
    else:
        cmd_args = list(cmd_args)
        command = cmd_args.pop(0)

        if command == "version":
            cli_version()

        if command == "help":
            help_ = True
            if not len(cmd_args):
                cli_help()
            elif cmd_args == ['all']:
                print_command_list()
                sys.exit(0)
            else:
                command = cmd_args.pop(0)

        if command in ALIASES:
            command = ALIASES[command]

        if command not in commands:
            possible_cmds = [
                cmd for cmd in commands if cmd.startswith(command)
            ]
            if len(possible_cmds) == 0:
                raise click.ClickException(
                    f"cylc {command}: unknown utility. Abort.\n"
                    'Type "cylc help all" for a list of utilities.'
                )
            elif len(possible_cmds) > 1:
                click.echo(
                    "cylc {}: is ambiguous for:\n{}".format(
                        command,
                        "\n".join(
                            [
                                "    cylc {}".format(cmd[5:])
                                for cmd in possible_cmds
                            ]
                        ),
                    ),
                    err=True,
                )
                sys.exit(1)
            else:
                command = possible_cmds[0]

        if command == "graph-diff":
            if len(cmd_args) > 2:
                for arg in cmd_args[2:]:
                    if arg.startswith("-"):
                        cmd_args.insert(cmd_args.index(arg), "--")
                        break
        elif command == "jobs-submit":
            if len(cmd_args) > 1:
                for arg in cmd_args:
                    if not arg.startswith("-"):
                        cmd_args.insert(cmd_args.index(arg) + 1, "--")
                        break
        elif command == "message":
            if cmd_args:
                if cmd_args[0] in ['-s', '--severity', '-p', '--priority']:
                    dd_index = 2
                else:
                    dd_index = 0
                cmd_args.insert(dd_index, "--")

        if help_:
            execute_cmd(command, "--help")
        else:
            if version:
                cmd_args.append("--version")
            execute_cmd(command, *cmd_args)
