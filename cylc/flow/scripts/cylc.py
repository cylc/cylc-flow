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

import click
import pkg_resources

from cylc.flow import __version__

# These will be ported to python as click commands
bash_commands = ["cylc-graph-diff", "cylc-jobscript", "cylc-scp-transfer"]

# First step of the click port, the list won't be necessary after that
command_list = bash_commands + list(
    pkg_resources.get_entry_map("cylc-flow").get("console_scripts").keys()
)

category_list = [
    "control",
    "information",
    "all",
    "task",
    "admin",
    "preparation",
    "discovery",
    "utility",
    "util",
    "prep",
    "con",
    "info",
]


def execute_cmd(cmd, *args):
    # Replace the current process with that of the sub-command.
    try:
        os.execvp(cmd, [cmd] + list(args))  # nosec
    except OSError as exc:
        if exc.filename is None:
            exc.filename = cmd
        raise click.ClickException(exc)
    else:
        sys.exit()


CONTEXT_SETTINGS = dict(ignore_unknown_options=True)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--help", "-h", "help_", is_flag=True, is_eager=True)
@click.option("--version", "-V", is_flag=True, is_eager=True)
@click.argument("cmd-args", nargs=-1)
def main(cmd_args, version, help_):
    if not cmd_args:
        if version:
            click.echo(__version__)
        else:
            execute_cmd("cylc-help")
    else:
        cmd_args = list(cmd_args)
        command = cmd_args.pop(0)
        if command in ["categories", "commands"] + category_list:
            if not cmd_args:
                execute_cmd("cylc-help", command)
                sys.exit(0)
            else:
                command = cmd_args.pop(0)

        if command == "version":
            click.echo(__version__)
        elif command:
            # to match bash script behavior
            if command == "h":
                command = "help"

            if command == "help":
                help_ = True
                if not len(cmd_args):
                    execute_cmd("cylc-help")
                    sys.exit(0)
                else:
                    cmd = cmd_args.pop(0)
                    if cmd in category_list:
                        if len(cmd_args) == 0:
                            execute_cmd("cylc-help", cmd)
                            sys.exit(0)
                        else:
                            command = cmd_args.pop(0)
                    else:
                        command = cmd

            cylc_cmd = f"cylc-{command}"

            if cylc_cmd not in command_list:
                possible_cmds = [
                    cmd for cmd in command_list if cmd.startswith(cylc_cmd)
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
                    cylc_cmd = possible_cmds[0]

            if cylc_cmd.endswith("graph-diff"):
                if len(cmd_args) > 2:
                    for arg in cmd_args[2:]:
                        if arg.startswith("-"):
                            cmd_args.insert(cmd_args.index(arg), "--")
                            break
            elif cylc_cmd.endswith("jobs-submit"):
                if len(cmd_args) > 1:
                    for arg in cmd_args:
                        if not arg.startswith("-"):
                            cmd_args.insert(cmd_args.index(arg) + 1, "--")
                            break
            elif cylc_cmd.endswith("message"):
                if cmd_args:
                    if cmd_args[0] in ['-s', '--severity', '-p', '--priority']:
                        dd_index = 2
                    else:
                        dd_index = 0
                    cmd_args.insert(dd_index, "--")

            if help_:
                execute_cmd(cylc_cmd, "--help")
            else:
                if version:
                    cmd_args.append("--version")
                execute_cmd(cylc_cmd, *cmd_args)
        elif help_:
            execute_cmd("cylc-help")


if __name__ == "__main__":
    main()
