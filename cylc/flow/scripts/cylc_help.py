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
"""temp"""

import sys

from colorama import init as color_init

from cylc.flow.exceptions import CylcError
from cylc.flow.scripts import cylc_header
from cylc.flow.terminal import cli_function, centered, format_shell_examples


color_init(autoreset=True, strip=False)


class CommandError(CylcError):
    pass


class CommandNotFoundError(CommandError):
    pass


class CommandNotUniqueError(CommandError):
    pass


def is_help(arg):
    """Return True if arg looks like a "help" command."""
    return (arg in ('-h', '--help', '--hlep', 'help', 'hlep', '?'))


def match_command(abbrev):
    """Allow any unique abbrev to commands when no category is specified"""
    matches = set()
    for com, aliases in commands.items():
        if any(alias == abbrev for alias in aliases):
            matches.clear()
            matches.add(com)
            break
        if any(alias.startswith(abbrev) for alias in aliases):
            matches.add(com)
    if not matches:
        raise CommandNotFoundError('COMMAND not found: ' + abbrev)
    if len(matches) > 1:
        # multiple matches
        raise CommandNotUniqueError('COMMAND "%s" not unique: %s' % (
            abbrev,
            ' '.join('|'.join(commands[com]) for com in matches)))
    return matches.pop()


def pretty_print(incom, choose_dict, indent=True, numbered=False, sort=False):
    # pretty print commands or topics from a dict:
    # (com[item] = description)

    if indent:
        spacer = ' '
    else:
        spacer = ''

    label = {}
    choose = []
    longest = 0
    for item in choose_dict:
        choose.append(item)
        lbl = '|'.join(choose_dict[item])
        label[item] = lbl
        if len(lbl) > longest:
            longest = len(lbl)

    count = 0
    pad = False
    if len(choose) > 9:
        pad = True

    if sort:
        choose.sort()
    for item in choose:
        if item not in incom:
            raise SystemExit("ERROR: summary for '" + item + "' not found")

        print(spacer, end=' ')
        if numbered:
            count += 1
            if pad and count < 10:
                digit = ' ' + str(count)
            else:
                digit = str(count)
            print(digit + '/', end=' ')
        print("%s %s %s" % (
            label[item],
            '.' * (longest - len(label[item])) + '...',
            incom[item]))


desc = '''
Cylc ("silk") is a workflow engine for orchestrating complex *suites* of
inter-dependent distributed cycling (repeating) tasks, as well as ordinary
non-cycling workflows.
'''

# BEGIN MAIN
usage = f"""
{cylc_header()}
{centered(desc)}

USAGE:
  $ cylc validate FLOW            # validate a workflow definition
  $ cylc run FLOW                 # run a workflow
  $ cylc tui FLOW                 # view a running workflow in the terminal
  $ cylc stop FLOW                # stop a running workflow

  $ cylc --version                # print cylc version

Commands can be abbreviated as long as there is no ambiguity in
the abbreviated command:
  $ cylc trigger SUITE TASK       # trigger TASK in SUITE
  $ cylc trig SUITE TASK          # ditto
  $ cylc tr SUITE TASK            # ditto
  $ cylc get                      # Error: ambiguous command

TASK IDENTIFICATION IN CYLC SUITES
  Tasks are identified by NAME.CYCLE_POINT where POINT is either a
  date-time or an integer.

  Date-time cycle points are in an ISO 8601 date-time format, typically
  CCYYMMDDThhmm followed by a time zone - e.g. 20101225T0600Z.

  Integer cycle points (including those for one-off suites) are integers
  - just '1' for one-off suites.
"""

usage = format_shell_examples(usage)

commands = {}
commands['broadcast'] = ['broadcast', 'bcast']
commands['cat-log'] = ['cat-log', 'log']
commands['check-software'] = ['check-software']
commands['check-versions'] = ['check-versions']
commands['checkpoint'] = ['checkpoint']
commands['client'] = ['client']
commands['cycle-point'] = [
    'cycle-point', 'cyclepoint', 'datetime', 'cycletime']
commands['diff'] = ['diff', 'compare']
commands['dump'] = ['dump']
commands['edit'] = ['edit']
commands['ext-trigger'] = ['ext-trigger', 'external-trigger']
commands['extract-resources'] = ['extract-resources']
commands['function-run'] = ['function-run']
commands['get-directory'] = ['get-directory']
commands['get-site-config'] = ['get-site-config', 'get-global-config']
commands['get-suite-config'] = ['get-suite-config', 'get-config']
commands['get-suite-contact'] = ['get-suite-contact', 'get-contact']
commands['get-suite-version'] = ['get-suite-version', 'get-cylc-version']
commands['graph'] = ['graph']
commands['graph-diff'] = ['graph-diff']
commands['hold'] = ['hold']
commands['jobs-kill'] = ['jobs-kill']
commands['jobs-poll'] = ['jobs-poll']
commands['jobs-submit'] = ['jobs-submit']
commands['kill'] = ['kill']
commands['list'] = ['list', 'ls']
commands['list'] = ['list', 'ls']
commands['ls-checkpoints'] = ['ls-checkpoints']
commands['message'] = ['message', 'task-message']
commands['nudge'] = ['nudge']
commands['ping'] = ['ping']
commands['poll'] = ['poll']
commands['print'] = ['print']
commands['psutil'] = ['psutil']
commands['register'] = ['register']
commands['release'] = ['release', 'unhold']
commands['reload'] = ['reload']
commands['remote-init'] = ['remote-init']
commands['remote-tidy'] = ['remote-tidy']
commands['remove'] = ['remove']
commands['report-timings'] = ['report-timings']
commands['restart'] = ['restart']
commands['run'] = ['run', 'start']
# NOTE: don't change 'run' to 'start' or the category [control]
# becomes compulsory to disambiguate from 'cylc [task] started'.
# Keeping 'start' as an alias however: 'cylc con start'.
commands['scan'] = ['scan']
commands['search'] = ['search', 'grep']
commands['set-outputs'] = ['set-outputs']
commands['set-verbosity'] = ['set-verbosity']
commands['show'] = ['show']
commands['stop'] = ['stop', 'shutdown']
commands['submit'] = ['submit', 'single']
commands['subscribe'] = ['subscribe']
commands['suite-state'] = ['suite-state']
commands['trigger'] = ['trigger']
commands['tui'] = ['tui']
commands['validate'] = ['validate']
commands['view'] = ['view']

# command summaries
comsum = {}
comsum['check-software'] = 'Check required software is installed'
comsum['register'] = 'Register a suite for use'
comsum['print'] = 'Print registered suites'
comsum['get-directory'] = 'Retrieve suite source directory paths'
comsum['edit'] = 'Edit suite definitions, optionally inlined'
comsum['view'] = 'View suite definitions, inlined and Jinja2 processed'
comsum['validate'] = 'Parse and validate suite definitions'
comsum['search'] = 'Search in suite definitions'
comsum['graph'] = 'Plot suite dependency graphs and runtime hierarchies'
comsum['graph-diff'] = 'Compare two suite dependencies or runtime hierarchies'
comsum['diff'] = 'Compare two suite definitions and print differences'
comsum['list'] = 'List suite tasks and family namespaces'
comsum['dump'] = 'Print the state of tasks in a running suite'
comsum['show'] = 'Print task state (prerequisites and outputs etc.)'
comsum['cat-log'] = 'Print various suite and task log files'
comsum['extract-resources'] = 'Extract cylc.flow library package resources'
comsum['tui'] = 'A terminal user interface for suites.'
comsum['get-suite-config'] = 'Print suite configuration items'
comsum['get-site-config'] = 'Print site/user configuration items'
comsum['get-suite-contact'] = (
    'Print contact information of a suite server program')
comsum['get-suite-version'] = 'Print cylc version of a suite server program'
comsum['run'] = 'Start a suite at a given cycle point'
comsum['stop'] = 'Shut down running suites'
comsum['restart'] = 'Restart a suite from a previous state'
comsum['trigger'] = 'Manually trigger any tasks'
comsum['remove'] = 'Remove task instances from scheduler task pool'
comsum['poll'] = 'Poll submitted or running tasks'
comsum['kill'] = 'Kill submitted or running tasks'
comsum['hold'] = 'Hold (pause) suites or individual tasks'
comsum['release'] = 'Release (unpause) suites or individual tasks'
comsum['set-outputs'] = 'Set task outputs as completed'
comsum['nudge'] = 'Cause the cylc task processing loop to be invoked'
comsum['reload'] = 'Reload the suite definition at run time'
comsum['set-verbosity'] = 'Change a running suite\'s logging verbosity'
comsum['broadcast'] = 'Change suite [runtime] settings on the fly'
comsum['ext-trigger'] = 'Report an external trigger event to a suite'
comsum['checkpoint'] = 'Tell suite to checkpoint its current state'
comsum['client'] = '(Internal) Invoke suite runtime client, expect JSON input'
comsum['subscribe'] = '(Internal) Invoke suite subscriber'
comsum['ping'] = 'Check that a suite is running'
comsum['scan'] = 'Scan a host for running suites'
comsum['check-versions'] = 'Compare cylc versions on task host accounts'
comsum['submit'] = 'Run a single task just as its parent suite would'
comsum['message'] = 'Report task messages'
comsum['jobs-kill'] = '(Internal) Kill task jobs'
comsum['jobs-poll'] = '(Internal) Retrieve status for task jobs'
comsum['jobs-submit'] = '(Internal) Submit task jobs'
comsum['remote-init'] = '(Internal) Initialise a task remote'
comsum['remote-tidy'] = '(Internal) Tidy a task remote'
comsum['cycle-point'] = 'Cycle point arithmetic and filename templating'
comsum['suite-state'] = 'Query the task states in a suite'
comsum['ls-checkpoints'] = 'Display task pool etc at given events'
comsum['report-timings'] = 'Generate a report on task timing data'
comsum['function-run'] = '(Internal) Run a function in the process pool'
comsum['psutil'] = '(Internal) Report information about the usage of a host'


class ArgumentParser:

    @classmethod
    def parse(cls):
        return cls

    @staticmethod
    def parse_args():
        return (None, [])


@cli_function(ArgumentParser.parse)
def main(*_):
    print(usage)
    sys.exit(0)


if __name__ == "__main__":
    main()
