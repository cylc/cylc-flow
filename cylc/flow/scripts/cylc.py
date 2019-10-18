#!/usr/bin/env python
# Copyright (C) 2008-2017 NIWA
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
import os

import click
import pkg_resources

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
        raise SystemExit(exc)


@click.command(context_settings={"ignore_unknown_options": True})
@click.option("--help", "-h", "help_", is_flag=True)
@click.argument("command")
@click.argument("cmd-args", nargs=-1)
@click.version_option()
def main(command, cmd_args, help_):
    if command in ["categories", "commands"] + category_list:
        execute_cmd("cylc-help", command)
    elif command:
        # to match bash script behavior
        if command == "h":
            command = "help"

        cylc_cmd = f"cylc-{command}"

        if cylc_cmd not in command_list:
            possible_cmds = [
                cmd for cmd in command_list if cmd.startswith(cylc_cmd)
            ]
            if len(possible_cmds) == 0:
                click.echo(f"cylc {command}: unknown utility. Abort.")
                click.echo('Type "cylc help all" for a list of utilities.')
                return -1
            elif len(possible_cmds) > 1:
                click.echo(
                    "cylc {}: is ambiguous for: {}".format(
                        command, [cmd[5:] for cmd in possible_cmds]
                    )
                )
                return -1
            else:
                cylc_cmd = possible_cmds[0]

        if help_:
            execute_cmd(cylc_cmd, "--help")
        else:
            execute_cmd(cylc_cmd, *list(cmd_args))
    elif help_:
        execute_cmd("cylc-help")

if __name__ == "__main__":
    main()
