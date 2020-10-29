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
    get_width,
    print_contents
)


desc = '''
Cylc ("silk") is a workflow engine for orchestrating complex *suites* of
inter-dependent distributed cycling (repeating) tasks, as well as ordinary
non-cycling workflows.
'''

# BEGIN MAIN
usage = f"""{cylc_header()}
{centered(desc)}

Usage:
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
usage = format_shell_examples(usage)
usage = cparse(usage)
color_init(autoreset=True, strip=False)
# TODO ^ this is causing the job submit errors due to control chars

# These will be ported to python as click commands
bash_commands = {
    'graph-diff': (
        'Compare the graphs of two workflows in text format.',
        'cylc graph-diff [OPTIONS] SUITE1 SUITE2 -- '
        '[GRAPH_OPTIONS_ARGS]'
    )
}

# First step of the click port, the list won't be necessary after that
commands = {
    # TODO: remove the cylc-flow constraint
    **pkg_resources.get_entry_map("cylc-flow").get("cylc.command"),
    **{
        cmd: None
        for cmd in bash_commands
    }
}


def execute_bash(cmd, *args):
    # Replace the current process with that of the sub-command.
    cmd = f'cylc-{cmd}'
    try:
        os.execvp(cmd, [cmd] + list(args))  # nosec
    except OSError as exc:
        if exc.filename is None:
            exc.filename = cmd
        raise click.ClickException(exc)


def execute_python(cmd, *args):
    commands[cmd].resolve()(*args)


def execute_cmd(cmd, *args):
    sys.stderr.write(f'$$$ {cmd} {" ".join(args)}')
    if cmd in bash_commands:
        execute_bash(cmd, *args)
    else:
        execute_python(cmd, *args)
    sys.exit()


CONTEXT_SETTINGS = dict(ignore_unknown_options=True)


def cli_help():
    print(usage)
    sys.exit(0)


def cli_version():
    click.echo(__version__)
    sys.exit(0)


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


@click.command(context_settings=CONTEXT_SETTINGS)
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
    # elif help_:
    #     cli_help()


def parse_docstring(docstring):
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


# def list_cmds():
def main2():
    contents = [
        (cmd, desc)
        for cmd, desc, _, in get_command_info()
    ]
    print_contents(contents)


def get_command_info():
    ret = []
    for cmd, obj in sorted(commands.items()):
        if cmd == 'cylc':
            continue
        if cmd == 'cylc-help':
            continue
        if obj:
            # python command
            module = __import__(obj.module_name, fromlist=[''])
            if getattr(module, 'INTERNAL', False):
                # do not list internal commands
                continue
            usage, desc = parse_docstring(module.__doc__)
            ret.append((cmd, desc, usage))
        elif cmd in bash_commands:
            # bash command
            desc, usage = bash_commands[cmd]
            ret.append((cmd, desc, usage))
        else:
            raise ValueError(f'Unrecognised command "{cmd}"')
    return ret
