#!/usr/bin/env python3

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

import sys

from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.exceptions import CylcError
from cylc.flow.terminal import cli_function


class CommandError(CylcError):
    pass


class CommandNotFoundError(CommandError):
    pass


class CommandNotUniqueError(CommandError):
    pass


def is_help(arg):
    """Return True if arg looks like a "help" command."""
    return (arg in ('-h', '--help', '--hlep', 'help', 'hlep', '?'))


def match_dict(abbrev, categories, title):
    """Allow any unique abbreviation to cylc categories"""
    matches = set()
    for cat, aliases in categories.items():
        if any(alias == abbrev for alias in aliases):
            # Exact match, don't look for more
            matches.clear()
            matches.add(cat)
            break
        if any(alias.startswith(abbrev) for alias in aliases):
            # Partial match
            matches.add(cat)
    if not matches:
        raise CommandNotFoundError(title + ' not found: ' + abbrev)
    if len(matches) > 1:
        # multiple matches
        raise CommandNotUniqueError('%s "%s" not unique: %s' % (
            title, abbrev,
            ' '.join('|'.join(categories[cat]) for cat in matches)))
    return matches.pop()


def match_command(abbrev):
    """Allow any unique abbrev to commands when no category is specified"""
    matches = set()
    finished_matching = False
    for dct in [admin_commands,
                preparation_commands,
                information_commands,
                discovery_commands,
                control_commands,
                utility_commands,
                task_commands]:
        for com, aliases in dct.items():
            if any(alias == abbrev for alias in aliases):
                matches.clear()
                matches.add(com)
                finished_matching = True
                break
            if any(alias.startswith(abbrev) for alias in aliases):
                matches.add(com)
        if finished_matching:
            break
    if not matches:
        raise CommandNotFoundError('COMMAND not found: ' + abbrev)
    if len(matches) > 1:
        # multiple matches
        raise CommandNotUniqueError('COMMAND "%s" not unique: %s' % (
            abbrev,
            ' '.join('|'.join(all_commands[com]) for com in matches)))
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


def category_help(category):
    coms = eval(category + '_commands')
    alts = '|'.join(categories[category])
    print('CATEGORY: ' + alts + ' - ' + catsum[category])
    print()
    print('HELP: cylc [' + alts + '] COMMAND help,--help')
    print('  You can abbreviate ' + alts + ' and COMMAND.')
    print('  The category ' + alts + ' may be omitted.')
    print()
    print('COMMANDS:')
    pretty_print(comsum, coms, sort=True)


# BEGIN MAIN
general_usage = f"""Cylc ("silk") is a workflow engine for orchestrating
complex *suites* of inter-dependent distributed cycling (repeating) tasks, as
well as ordinary non-cycling workflows.
For detailed documentation see the Cylc User Guide (cylc doc --help).

Version {CYLC_VERSION}

USAGE:
  % cylc -V,--version,version           # print cylc version
  % cylc version --long                 # print cylc version and path
  % cylc help,--help,-h,?               # print this help page

  % cylc help CATEGORY                  # print help by category
  % cylc CATEGORY help                  # (ditto)
  % cylc help [CATEGORY] COMMAND        # print command help
  % cylc [CATEGORY] COMMAND --help      # (ditto)
  % cylc COMMAND --help                 # (ditto)

  % cylc COMMAND [options] SUITE [arguments]
  % cylc COMMAND [options] SUITE TASK [arguments]"""

usage = general_usage + """

Commands can be abbreviated as long as there is no ambiguity in
the abbreviated command:

  % cylc trigger SUITE TASK             # trigger TASK in SUITE
  % cylc trig SUITE TASK                # ditto
  % cylc tr SUITE TASK                  # ditto

  % cylc get                            # Error: ambiguous command

TASK IDENTIFICATION IN CYLC SUITES
  Tasks are identified by NAME.CYCLE_POINT where POINT is either a
  date-time or an integer.
  Date-time cycle points are in an ISO 8601 date-time format, typically
  CCYYMMDDThhmm followed by a time zone - e.g. 20101225T0600Z.
  Integer cycle points (including those for one-off suites) are integers
  - just '1' for one-off suites.

HOW TO DRILL DOWN TO COMMAND USAGE HELP:
  % cylc help           # list all available categories (this page)
  % cylc help prep      # list commands in category 'preparation'
  % cylc help prep edit # command usage help for 'cylc [prep] edit'

Command CATEGORIES:"""

# categories[category] = [aliases]
categories = {}
categories['all'] = ['all']
categories['preparation'] = ['preparation']
categories['information'] = ['information']
categories['discovery'] = ['discovery']
categories['control'] = ['control']
categories['utility'] = ['utility']
categories['task'] = ['task']
categories['admin'] = ['admin']

information_commands = {}

information_commands['list'] = ['list', 'ls']
information_commands['dump'] = ['dump']
information_commands['show'] = ['show']
information_commands['cat-log'] = ['cat-log', 'log']
information_commands['extract-resources'] = ['extract-resources']
information_commands['get-suite-contact'] = [
    'get-suite-contact', 'get-contact']
information_commands['get-suite-version'] = [
    'get-suite-version', 'get-cylc-version']

information_commands['tui'] = ['tui']
information_commands['get-suite-config'] = ['get-suite-config', 'get-config']
information_commands['get-site-config'] = [
    'get-site-config', 'get-global-config']

control_commands = {}
# NOTE: don't change 'run' to 'start' or the category [control]
# becomes compulsory to disambiguate from 'cylc [task] started'.
# Keeping 'start' as an alias however: 'cylc con start'.
control_commands['run'] = ['run', 'start']
control_commands['stop'] = ['stop', 'shutdown']
control_commands['restart'] = ['restart']
control_commands['trigger'] = ['trigger']
control_commands['remove'] = ['remove']
control_commands['poll'] = ['poll']
control_commands['kill'] = ['kill']
control_commands['hold'] = ['hold']
control_commands['release'] = ['release', 'unhold']
control_commands['set-outputs'] = ['set-outpus']
control_commands['nudge'] = ['nudge']
control_commands['reload'] = ['reload']
control_commands['set-verbosity'] = ['set-verbosity']
control_commands['broadcast'] = ['broadcast', 'bcast']
control_commands['ext-trigger'] = ['ext-trigger', 'external-trigger']
control_commands['checkpoint'] = ['checkpoint']
control_commands['client'] = ['client']
control_commands['subscribe'] = ['subscribe']

utility_commands = {}
utility_commands['cycle-point'] = [
    'cycle-point', 'cyclepoint', 'datetime', 'cycletime']
utility_commands['suite-state'] = ['suite-state']
utility_commands['ls-checkpoints'] = ['ls-checkpoints']
utility_commands['report-timings'] = ['report-timings']
utility_commands['function-run'] = ['function-run']
utility_commands['psutil'] = ['psutil']

admin_commands = {}
admin_commands['check-software'] = ['check-software']

preparation_commands = {}
preparation_commands['register'] = ['register']
preparation_commands['print'] = ['print']
preparation_commands['get-directory'] = ['get-directory']
preparation_commands['edit'] = ['edit']
preparation_commands['view'] = ['view']
preparation_commands['validate'] = ['validate']
preparation_commands['list'] = ['list', 'ls']
preparation_commands['search'] = ['search', 'grep']
preparation_commands['graph'] = ['graph']
preparation_commands['graph-diff'] = ['graph-diff']
preparation_commands['diff'] = ['diff', 'compare']

discovery_commands = {}
discovery_commands['ping'] = ['ping']
discovery_commands['scan'] = ['scan']
discovery_commands['check-versions'] = ['check-versions']

task_commands = {}
task_commands['submit'] = ['submit', 'single']
task_commands['message'] = ['message', 'task-message']
task_commands['jobs-kill'] = ['jobs-kill']
task_commands['jobs-poll'] = ['jobs-poll']
task_commands['jobs-submit'] = ['jobs-submit']
task_commands['remote-init'] = ['remote-init']
task_commands['remote-tidy'] = ['remote-tidy']

all_commands = {}
for dct in [
        preparation_commands,
        information_commands,
        discovery_commands,
        control_commands,
        utility_commands,
        task_commands,
        admin_commands]:
    all_commands.update(dct)

# topic summaries
catsum = {}
catsum['all'] = "The complete command set."
catsum['admin'] = "Cylc installation, testing, and example suites."
catsum['information'] = "Interrogate suite definitions and running suites."
catsum['preparation'] = "Suite editing, validation, visualization, etc."
catsum['discovery'] = "Detect running suites."
catsum['control'] = "Suite start up, monitoring, and control."
catsum['task'] = "The task messaging interface."
catsum['utility'] = "Cycle arithmetic and templating, etc."

# Some commands and categories are aliased and
# some common typographical errors are corrected (e.g. cycl => cylc).

# command summaries
comsum = {}
# admin
comsum['check-software'] = 'Check required software is installed'
# preparation
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
# information
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
# control
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
# discovery
comsum['ping'] = 'Check that a suite is running'
comsum['scan'] = 'Scan a host for running suites'
comsum['check-versions'] = 'Compare cylc versions on task host accounts'
# task
comsum['submit'] = 'Run a single task just as its parent suite would'
comsum['message'] = 'Report task messages'
comsum['jobs-kill'] = '(Internal) Kill task jobs'
comsum['jobs-poll'] = '(Internal) Retrieve status for task jobs'
comsum['jobs-submit'] = '(Internal) Submit task jobs'
comsum['remote-init'] = '(Internal) Initialise a task remote'
comsum['remote-tidy'] = '(Internal) Tidy a task remote'

# utility
comsum['cycle-point'] = 'Cycle point arithmetic and filename templating'
comsum['suite-state'] = 'Query the task states in a suite'
comsum['ls-checkpoints'] = 'Display task pool etc at given events'
comsum['report-timings'] = 'Generate a report on task timing data'
comsum['function-run'] = '(Internal) Run a function in the process pool'
comsum['psutil'] = '(Internal) Report information about the usage of a host'


def help_func():
    # no arguments: print help and exit
    if len(sys.argv) == 1:
        print(usage.replace("__CYLC_VERSION__", CYLC_VERSION))
        pretty_print(catsum, categories)
        sys.exit(0)

    args = sys.argv[1:]

    if len(args) == 1:
        if args[0] == 'categories':
            # secret argument for document processing
            for key in sorted(catsum):
                print(key)
            sys.exit(0)
        if args[0] == 'commands':
            # secret argument for document processing
            for key in sorted(comsum):
                print(key)
            sys.exit(0)
        if args[0].startswith('category='):
            # secret argument for gcylc
            category = args[0][9:]
            commands = eval(category + '_commands')
            for command in commands:
                print(command)
            sys.exit(0)
        if is_help(args[0]):
            # cylc help
            print(usage)
            pretty_print(catsum, categories)
            sys.exit(0)
        if (args[0] in ['--version', '-V']):
            print(CYLC_VERSION)
            sys.exit(0)

        # cylc CATEGORY with no args => category help
        try:
            category = match_dict(args[0], categories, 'CATEGORY')
        except CommandError:
            # No matching category
            # (no need to print this, the exception will recur below)
            # Carry on in case of a no-argument command (e.g. 'cylc scan')
            pass
        else:
            category_help(category)
            sys.exit(0)

    if len(args) == 2 and (is_help(args[0]) or is_help(args[1])):
        # TWO ARGUMENTS, one help
        # cylc help CATEGORY
        # cylc CATEGORY help
        # cylc help COMMAND
        # cylc COMMAND help
        if is_help(args[1]):
            item = args[0]
        else:
            item = args[1]
        try:
            category = match_dict(item, categories, 'CATEGORY')
        except CommandError as exc:
            # no matching category, try command
            try:
                command = match_command(item)
            except CommandError as exc2:
                print(exc, file=sys.stderr)
                raise SystemExit(exc2)
        else:
            # cylc help CATEGORY
            category_help(category)
            sys.exit(0)


class ArgumentParser:

    @classmethod
    def parse(cls):
        return cls

    @staticmethod
    def parse_args():
        help_func()
        return (None, None)


@cli_function(ArgumentParser.parse)
def main():
    pass


if __name__ == "__main__":
    main()
