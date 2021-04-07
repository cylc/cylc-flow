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
"""cylc scan [OPTIONS]

List Cylc workflows.

By default this shows only running or paused workflows.

Examples:
  # list all "active" workflows (i.e. running or paused)
  $ cylc scan

  # show more information about these workflows
  $ cylc scan -t rich

  # don't rely on colour for job state totals
  $ cylc scan -t rich --colour-blind

  # list all "inactive" workflows (i.e. registered or stopped)
  $ cylc scan --state stopped

  # list all workflows (active or inactive)
  $ cylc scan --state=running,paused,stopped
  $ cylc scan --state=all  # or using the shorthand

  # filter workflows by name
  $ cylc scan --name '^f.*'  # show only flows starting with "f"

  # get results in JSON format
  $ cylc scan -t json
"""

import asyncio
import json
from pathlib import Path

from ansimarkup import ansiprint as cprint

from cylc.flow import LOG
from cylc.flow.exceptions import UserInputError
from cylc.flow.network.scan import (
    scan,
    is_active,
    contact_info,
    graphql_query,
    filter_name
)
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    Options
)
from cylc.flow.print_tree import get_tree
from cylc.flow.suite_files import ContactFileFields as Cont
from cylc.flow.terminal import cli_function


# default grey colour (do not use "dim", it is not sufficiently portable)
DIM = 'fg 248'

# all supported states
FLOW_STATES = {
    'running',
    'paused',
    'stopping',
    'stopped'
}


# status colours
FLOW_STATE_CMAP = {
    # state: term colour
    'running': 'green',
    'paused': 'fg 172',
    'stopping': 'fg 201',
    'stopped': 'red'
}


# status symbols
FLOW_STATE_SYMBOLS = {
    # NOTE: the standard media control characters ▶️,, ⏸️,, ⏹️
    #       can appear wildly different font-depending and may not
    #       even be monospace
    'running': '▶',
    'paused': '‖',
    'stopping': '◧',
    'stopped': '■'
}


# document the flow states
__doc__ += '\n    '.join(
    [
        '\nWorkflow States:'
    ] + [
        (
            f'<{FLOW_STATE_CMAP[state]}>'
            f'{FLOW_STATE_SYMBOLS[state]}'
            f' {state}'
            f'</{FLOW_STATE_CMAP[state]}>'
        )
        for state in FLOW_STATES
    ]
)


# job icon colours
JOB_COLOURS = {
    # job status: term colour
    'submitted': 'fg 44',
    'submit-failed': 'fg 13',
    'running': 'fg 32',
    'succeeded': 'fg 35',
    'failed': 'fg 124'
}


# document the task states
__doc__ += '\n    '.join(
    [
        '\n\nTask States:'
    ] + [
        f'<{tag}>■ {state}</{tag}>'
        for state, tag in JOB_COLOURS.items()
    ]
)


# graphql fields to request from the workflow for the "rich" format
RICH_FIELDS = {
    'status': None,
    'stateTotals': None,
    'cylcVersion': None,
    'meta': {
        'title',
        'description',
    },

}


def get_option_parser():
    """CLI opts for "cylc scan"."""
    parser = COP(
        __doc__,
        comms=True,
        argdoc=[],
    )

    parser.add_option(
        '--name', '-n',
        help=(
            'Filter flows by registered name using a regex.'
            ' Can be used multiple times, workflows will be displayed if'
            ' their name matches ANY of the provided regexes.'
        ),
        action='append'
    )

    parser.add_option(
        '--states',
        help=(
            'Choose which flows to display by providing a list of states'
            ' or "all" to show everything. See the full `cylc scan` help'
            ' for a list of supported states.'
        ),
        default='running,paused,stopping',
        action='store'
    )

    parser.add_option(
        '--format', '-t',
        help=(
            'Set the output format.'
            ' (rich: multi-line, human readable)'
            ' (plain: single-line)'
            ' (json: machine readable)'
            ' (tree: display registration hierarchy as a tree)'
            ' (name: just show flow names, machine readable)'
        ),
        choices=('rich', 'plain', 'json', 'tree', 'name'),
        default='plain'
    )

    parser.add_option(
        '--sort',
        help='Sort flows by name before writing them (takes longer).',
        action='store_true'
    )

    parser.add_option(
        '--colour-blind', '--color-blind',
        help=(
            "Don't depend on colour to convey information. "
            ' Use this rather than --color=never so you still get bold text.'
        ),
        action='store_true'
    )

    parser.add_option(
        '--ping',
        help=(
            'Test the connection to the flow. Scan normally just reads flow'
            ' contact files, but --ping forces a connection to the scheduler'
            ' and removes the contact file if it is not found to be running'
            " (this can happen if the scheduler gets killed and can't clean"
            ' up after itself).'
        ),
        action='store_true'
    )

    return parser


def state_totals(totals, colour_blind=False):
    """Return a string with a visual representation of a suite's state totals.

    Args:
        totals (dict):
            State totals dictionary.
        colour_blind (bool):
            If True then we will not depend on colour to convey information.

    Returns:
        str

    """
    ret = []
    for state, tag in JOB_COLOURS.items():
        number = totals[state]
        if number == 0:
            continue
        if colour_blind:
            ret.append(f'<{tag}>{state}:{number}</{tag}>')
        else:
            ret.append(f'<{tag}>{number} ■</{tag}>')
    return ' '.join(ret)


def state_totals_key():
    """Return a key to accompany state_totals."""
    return '<b>Job State Key: </b>' + ' '.join(
        f'<{tag}>\u25A0 {name}</{tag}>'
        for name, tag in JOB_COLOURS.items()
    )


def _format_json(items, _):
    """A JSON formatter."""
    return json.dumps(
        [
            {
                key: str(value) if isinstance(value, Path) else value
                for key, value in flow.items()
            }
            for flow in items
        ],
        indent=4,
        sort_keys=True
    )


def _format_plain(flow, _):
    """A single line format of the form: <name> [<host>:<port>]"""
    if flow.get('contact'):
        return f'<b>{flow["name"]}</b> {flow[Cont.HOST]}:{flow[Cont.PORT]}'
    else:
        return f'<{DIM}><b>{flow["name"]}</b></{DIM}>'


def _format_name_only(flow, _):
    """A single line format of the form: <name> [<host>:<port>]"""
    return flow['name']


def _format_rich(flow, opts):
    """A multiline format which pulls in metadata."""
    status = flow.get('status', 'stopped')
    if opts.colour_blind:
        name = f'{flow["name"]} ({status})'
    else:
        symbol = FLOW_STATE_SYMBOLS[status]
        tag = FLOW_STATE_CMAP[status]
        name = f'<{tag}>{symbol}</{tag}> {flow["name"]}'
    if not flow.get('contact') or 'status' not in flow:
        ret = [f'<{DIM}><b>{name}</b></{DIM}>']
    else:
        ret = [f'<b>{name}</b>']

        display = {
            'state totals': state_totals(
                flow['stateTotals'], opts.colour_blind
            ),
            **{
                key: flow['meta'][key] or f'<{DIM}>*null*</{DIM}>'
                for key in (
                    'title',
                    'description'
                )
            },
            **{
                name: flow[key]
                for name, key in (
                    ('version', 'cylcVersion'),
                    ('host', Cont.HOST),
                    ('port', Cont.PORT)
                )
            }
        }
        maxlen = max(len(key) for key in display)
        for key, value in display.items():
            # format multiline strings by whitespace padding the lines
            value = ('\n' + (' ' * (maxlen + 7))).join(value.splitlines())
            # write out the key: value pairs
            ret.append(f'    {key: <{maxlen}}   {value}')
    return '\n'.join(ret)


def sort_function(flow):
    if flow.get('status') == 'running':
        state = 0
    elif flow.get('status') == 'paused':
        state = 0
    elif flow.get('contact'):
        state = 2
    else:
        state = 3
    return (state, flow['name'])


async def _sorted(pipe, formatter, opts, write):
    """List all flows, sort, then print them individually."""
    ret = []
    async for item in pipe:
        ret.append(item)
    for flow in sorted(ret, key=sort_function):
        write(formatter(flow, opts))


async def _serial(pipe, formatter, opts, write):
    """List all flows, then print them as one."""
    ret = []
    async for item in pipe:
        ret.append(item)
    write(formatter(ret, opts))


async def _async(pipe, formatter, opts, write):
    """List and print flows individually."""
    async for flow in pipe:
        write(formatter(flow, opts))


async def _tree(pipe, formatter, opts, write):
    """List all flows, sort, then print them as a tree."""
    # get list of flows
    ret = []
    async for flow in pipe:
        ret.append(flow)

    # construct tree
    tree = {}
    for flow in sorted(ret, key=lambda f: f['name']):
        parts = Path(flow['name']).parts
        pointer = tree
        for part in parts[:-1]:
            if part not in pointer:
                pointer[part] = {}
            pointer = pointer[part]
        flow['name'] = parts[-1]
        item = formatter(flow, opts)
        if len(parts) > 1:
            item = f' {item}'
        pointer[item] = ''

    # print tree
    ret = get_tree(tree, '', sort=False, use_unicode=True)
    write('\n'.join(ret))


def get_pipe(opts, formatter, scan_dir=None):
    """Construct a pipe for listing flows."""
    if scan_dir:
        pipe = scan(scan_dir=scan_dir)
    else:
        pipe = scan

    show_running = 'running' in opts.states
    show_paused = 'paused' in opts.states
    show_active = show_running or show_paused or 'stopping' in opts.states
    # show_active = bool({'running', 'paused'} & opts.states)
    show_inactive = bool({'stopped'} & opts.states)

    # filter by flow name
    if opts.name:
        pipe |= filter_name(*opts.name)

    # filter by flow state
    if show_active:
        pipe |= is_active(True, filter_stop=(not show_inactive))
    elif show_inactive:
        pipe |= is_active(False)

    # get contact file information
    if show_active:
        pipe |= contact_info

    graphql_fields = {}
    graphql_filters = set()

    # filter paused/running flows
    if show_active and not (show_running and show_paused):
        graphql_fields['status'] = None
        graphql_filters.add((('status',), tuple(opts.states)))

    # get fancy data if requested
    if formatter == _format_rich:
        # graphql_fields['status'] = None
        graphql_fields.update(RICH_FIELDS)

    # add graphql queries / filters to the pipe
    if show_active and graphql_fields:
        pipe |= graphql_query(graphql_fields, filters=graphql_filters)
    elif opts.ping:
        # check the flow is running even if not required
        # by display format or filters
        pipe |= graphql_query({'status': None})

    # yield results as they are processed
    pipe.preserve_order = False

    return pipe


def get_formatter(opts):
    """Return the appropriate formatter and method for the provided opts."""
    formatter = None
    method = None

    if opts.format == 'plain':
        formatter = _format_plain
        method = _async
    elif opts.format == 'json':
        formatter = _format_json
        method = _serial
    elif opts.format == 'rich':
        formatter = _format_rich
        method = _async
    elif opts.format == 'tree':
        formatter = _format_plain
        method = _tree
    elif opts.format == 'name':
        formatter = _format_name_only
        method = _async
    else:
        raise NotImplementedError

    if opts.sort and method == _serial:
        raise ValueError(f'--sort is incompatible with --format {opts.format}')
    elif opts.sort:
        method = _sorted

    return formatter, method


async def scanner(opts, write, scan_dir=None):
    """Print workflows to stdout."""
    formatter, method = get_formatter(opts)
    pipe = get_pipe(opts, formatter, scan_dir)

    LOG.debug(f'pipe: {repr(pipe)}')

    await method(pipe, formatter, opts, write)


async def main(opts, color=False, scan_dir=None, write=cprint):
    """Open up a Python API for testing purposes.

    Note:
        Don't use this API for anything other than testing, there is a
        proper Python API for these purposes.

    """
    # validate / standardise the list of workflow states
    opts.states = set(opts.states.split(','))
    if 'all' in opts.states:
        opts.states = FLOW_STATES
    elif (
        not opts.states
        or not all(
            state in FLOW_STATES
            for state in opts.states
        )
    ):
        raise UserInputError(
            '--states must be set to a comma separated list of workflow'
            ' states. \nSee `cylc scan --help` for a list of supported'
            ' states.'
        )

    if not color:
        # we cannot support colour or have been requested not to use it
        opts.colour_blind = True

    # print state totals key as needed
    if opts.format == 'rich' and not opts.colour_blind:
        cprint(state_totals_key() + '\n')

    await scanner(opts, write, scan_dir)


@cli_function(get_option_parser)
def cli(_, opts, color):
    """Implement `cylc scan`."""
    asyncio.run(
        main(opts, color)
    )


ScanOptions = Options(get_option_parser())
