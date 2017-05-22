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

# Cylc Help

from parsec.OrderedDict import OrderedDict


def category_help(category, categories):
    coms = eval(category + '_commands')
    alts = '|'.join(categories[category])
    print 'CATEGORY: ' + alts + ' - ' + catsum[category]
    print
    print 'HELP: cylc [' + alts + '] COMMAND help,--help'
    print '  You can abbreviate ' + alts + ' and COMMAND.'
    print '  The category ' + alts + ' may be omitted.'
    print
    print 'COMMANDS:'
    pretty_print(comsum, coms, sort=True)


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

        print spacer,
        if numbered:
            count += 1
            if pad and count < 10:
                digit = ' ' + str(count)
            else:
                digit = str(count)
            print digit + '/',
        print "%s %s %s" % (
            label[item],
            '.' * (longest - len(label[item])) + '...',
            incom[item])

# Some commands and categories are aliased and
# some common typographical errors are corrected (e.g. cycl => cylc).
# categories[category] = [aliases]


def comsum():
    # command summaries
    comsum = OrderedDict()
    # admin
    comsum['test-battery'] = 'Run a battery of self-diagnosing test suites'
    comsum['profile-battery'] = 'Run a battery of profiling tests'
    comsum['import-examples'] = 'Import example suites your suite run directory'
    comsum['upgrade-run-dir'] = 'Upgrade a pre-cylc-6 suite run directory'
    comsum['check-software'] = 'Check required software is installed.'
    # license
    comsum['warranty'] = 'Print the GPLv3 disclaimer of warranty'
    comsum['conditions'] = 'Print the GNU General Public License v3.0'
    # preparation
    comsum['register'] = 'Register a suite for use'
    comsum['print'] = 'Print registered suites'
    comsum['get-directory'] = 'Retrieve suite source directory paths'
    comsum['edit'] = 'Edit suite definitions, optionally inlined'
    comsum['view'] = 'View suite definitions, inlined and Jinja2 processed'
    comsum['validate'] = 'Parse and validate suite definitions'
    comsum['5to6'] = 'Improve the cylc 6 compatibility of a cylc 5 suite file'
    comsum['search'] = 'Search in suite definitions'
    comsum['graph'] = 'Plot suite dependency graphs and runtime hierarchies'
    comsum['graph-diff'] = 'Compare two suite dependencies or runtime hierarchies'
    comsum['diff'] = 'Compare two suite definitions and print differences'
    # information
    comsum['list'] = 'List suite tasks and family namespaces'
    comsum['dump'] = 'Print the state of tasks in a running suite'
    comsum['cat-state'] = 'Print the state of tasks from the state dump'
    comsum['show'] = 'Print task state (prerequisites and outputs etc.)'
    comsum['cat-log'] = 'Print various suite and task log files'
    comsum['documentation'] = 'Display cylc documentation (User Guide etc.)'
    comsum['monitor'] = 'An in-terminal suite monitor (see also gcylc)'
    comsum['get-suite-config'] = 'Print suite configuration items'
    comsum['get-site-config'] = 'Print site/user configuration items'
    comsum['get-gui-config'] = 'Print gcylc configuration items'
    comsum['get-suite-contact'] = 'Print the contact information of a suite daemon'
    comsum['get-suite-version'] = 'Print the cylc version of a suite daemon'
    comsum['version'] = 'Print the cylc release version'
    comsum['gscan'] = 'Scan GUI for monitoring multiple suites'
    comsum['gpanel'] = 'Internal interface for GNOME 2 panel applet'
    # control
    comsum['gui'] = '(a.k.a. gcylc) cylc GUI for suite control etc.'
    comsum['run'] = 'Start a suite at a given cycle point'
    comsum['stop'] = 'Shut down running suites'
    comsum['restart'] = 'Restart a suite from a previous state'
    comsum['trigger'] = 'Manually trigger or re-trigger a task'
    comsum['insert'] = 'Insert tasks into a running suite'
    comsum['remove'] = 'Remove tasks from a running suite'
    comsum['poll'] = 'Poll submitted or running tasks'
    comsum['kill'] = 'Kill submitted or running tasks'
    comsum['hold'] = 'Hold (pause) suites or individual tasks'
    comsum['release'] = 'Release (unpause) suites or individual tasks'
    comsum['reset'] = 'Force one or more tasks to change state.'
    comsum['spawn'] = 'Force one or more tasks to spawn their successors.'
    comsum['nudge'] = 'Cause the cylc task processing loop to be invoked'
    comsum['reload'] = 'Reload the suite definition at run time'
    comsum['set-runahead'] = 'Change the runahead limit in a running suite.'
    comsum['set-verbosity'] = 'Change a running suite\'s logging verbosity'
    comsum['ext-trigger'] = 'Report an external trigger event to a suite'
    comsum['checkpoint'] = 'Tell suite to checkpoint its current state'
    # discovery
    comsum['ping'] = 'Check that a suite is running'
    comsum['scan'] = 'Scan a host for running suites'
    comsum['check-versions'] = 'Compare cylc versions on task host accounts'
    # task
    comsum['submit'] = 'Run a single task just as its parent suite would'
    comsum['message'] = '(task messaging) Report task messages'
    comsum['broadcast'] = 'Change suite [runtime] settings on the fly'
    comsum['jobs-kill'] = '(Internal) Kill task jobs'
    comsum['jobs-poll'] = '(Internal) Retrieve status for task jobs'
    comsum['jobs-submit'] = '(Internal) Submit task jobs'

    # utility
    comsum['cycle-point'] = 'Cycle point arithmetic and filename templating'
    comsum['jobscript'] = 'Generate a task job script and print it to stdout'
    comsum['scp-transfer'] = 'Scp-based file transfer for cylc suites'
    comsum['suite-state'] = 'Query the task states in a suite'
    comsum['ls-checkpoints'] = 'Display task pool etc at given events'

    # hook
    comsum['email-task'] = 'A task event hook script that sends email alerts'
    comsum['email-suite'] = 'A suite event hook script that sends email alerts'
    comsum['job-logs-retrieve'] = (
        '(Internal) Retrieve logs from a remote host for a task job')
    comsum['check-triggering'] = 'A suite shutdown event hook for cylc testing'

    return comsum


def catsum():

    # topic summaries
    catsum = {}
    catsum['all'] = "The complete command set."
    catsum['admin'] = "Cylc installation, testing, and example suites."
    catsum['license'] = "Software licensing information (GPL v3.0)."
    catsum['information'] = "Interrogate suite definitions and running suites."
    catsum['preparation'] = "Suite editing, validation, visualization, etc."
    catsum['discovery'] = "Detect running suites."
    catsum['control'] = "Suite start up, monitoring, and control."
    catsum['task'] = "The task messaging interface."
    catsum['hook'] = "Suite and task event hook scripts."
    catsum['utility'] = "Cycle arithmetic and templating, etc."

    return catsum
