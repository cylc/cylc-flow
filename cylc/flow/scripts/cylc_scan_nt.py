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
"""cylc [discovery] scan-nt [OPTIONS]

List Cylc workflows, by default this shows only running or held workflows.

Examples:
    # list all "active" workflows (i.e. running or held)
    $ cylc scan-nt

    # show more information about these workfows
    $ cylc scan-nt -t rich

    # don't rely on colour for job state totals
    $ cylc scan-nt -t rich --colour-blind

    # list all "inactive" workflows (i.e. registered or stopped)
    $ cylc scan-nt --state stopped

    # list all workflows (active or inactive)
    $ cylc scan-nt --state=running,held,stopped
    $ cylc scan-nt --state=all  # or using the shorthand

    # filter workflows by name
    $ cylc scan-nt --name '^f.*'  # show only flows starting with "f"

    # get results in JSON format
    $ cylc scan-nt -t json
"""

import asyncio
import json
from pathlib import Path

from ansimarkup import ansiprint as cprint

from cylc.flow import LOG
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.scan_nt import (
    scan,
    is_active,
    contact_info,
    graphql_query,
    filter_name
)
from cylc.flow.suite_files import ContactFileFields as Cont
from cylc.flow.terminal import cli_function


FLOW_STATE_CMAP = {
    # suite state: term colour
    'running': 'green',
    'held': 'fg 172',
    'stopped': 'red'
}


FLOW_STATES = {
    'stopped',
    'held',
    'running'
}


def get_option_parser():
    """CLI opts for "cylc scan"."""
    parser = COP(
        __doc__,
        comms=True,
        noforce=True,
        argdoc=[],
    )

    parser.add_option(
        '--name',
        help=(
            'Filter flows by registered name using a regex.'
            ' Can be used multiple times, workflows will be displayed if'
            ' their name matches ANY of the provided regexes.'
        ),
        action='append'
    )

    parser.add_option(
        '--states',
        help='Choose which flows to display by providing a list of states.',
        default='running,held',
        action='store'
    )

    parser.add_option(
        '--format', '-t',
        help='Set the output format:',
        choices=('rich', 'plain', 'json'),
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
            'Write out job state names when displaying state totals rather'
            ' than relying on colour.'
        ),
        action='store_true'
    )

    return parser


def make_serial(flow):
    return {
        key: str(value)
        for key, value in flow.items()
    }


def _format_json(items, _):
    return json.dumps(
        [
            {
                key: str(value) if isinstance(value, Path) else value
                for key, value in flow.items()
            }
            for flow in items
        ],
        indent=4
    )


def _format_plain(flow, _):
    # <name> [<host>:<port>]
    if flow.get('contact'):
        return f'<b>{flow["name"]}</b> {flow[Cont.HOST]}:{flow[Cont.PORT]}'
    else:
        return f'<dim><b>{flow["name"]}</b></dim>'


RICH_FIELDS = {
    'status': None,
    'stateTotals': None,
    'meta': {
        'title',
        'description',
        # 'group',
        # 'url',
    },

}


JOB_COLOURS = {
    'submitted': 'fg 38',
    'submit-failed': 'fg 13',
    'running': 'fg 27',
    'succeeded': 'fg 34',
    'failed': 'fg 124'
}


def state_totals(totals, colour_blind=False):
    ret = []
    for state, tag in JOB_COLOURS.items():
        number = totals[state]
        if number == 0:
            continue
        if colour_blind:
            ret.append(f'<{tag}>{state}:{number}</{tag}>')
        else:
            ret.append(f'<{tag}>{number} \u25A0</{tag}>')
    return ' '.join(ret)


def state_totals_keys():
    return '<b>Job State Key: </b>' + ' '.join(
        f'<{tag}>\u25A0 {name}</{tag}>'
        for name, tag in JOB_COLOURS.items()
    )


def _format_rich(flow, opts):
    if not flow.get('contact'):
        ret = [f'<dim><b>{flow["name"]}</b> (stopped)</dim>']
    else:
        tag = FLOW_STATE_CMAP[flow['status']]
        ret = [
            f'<b>{flow["name"]}</b>'
            f' (<{tag}>{flow["status"]}</{tag}>)'
        ]

        display = {
            'state totals': state_totals(
                flow['stateTotals'], opts.colour_blind
            ),
            **{
                name: flow[key]
                for name, key in (('host', Cont.HOST), ('port', Cont.PORT))
            },
            **{
                key: flow['meta'][key] or '<dim>*null*</dim>'
                for key in ('title', 'description')
            }
        }
        maxlen = max(len(key) for key in display)
        for key, value in display.items():
            ret.append(f'    {key: <{maxlen}}   {value}')
    return '\n'.join(ret)


def sort_function(flow):
    if flow.get('status') == 'running':
        state = 0
    elif flow.get('status') == 'held':
        state = 0
    elif flow.get('contact'):
        state = 2
    else:
        state = 3
    return (state, flow['name'])


async def _sorted(pipe, formatter, opts):
    ret = []
    async for item in pipe:
        ret.append(item)
    for flow in sorted(ret, key=sort_function):
        cprint(formatter(flow, opts))


async def _serial(pipe, formatter, opts):
    ret = []
    async for item in pipe:
        ret.append(item)
    cprint(formatter(ret, opts))


async def _async(pipe, formatter, opts):
    async for flow in pipe:
        cprint(formatter(flow, opts))


def get_pipe(opts, formatter):
    pipe = scan

    show_running = 'running' in opts.states
    show_held = 'held' in opts.states
    show_active = show_running or show_held
    # show_active = bool({'running', 'held'} & opts.states)
    show_inactive = bool({'stopped'} & opts.states)
    show_all = show_active and show_inactive

    # filter by flow name
    if opts.name:
        pipe |= filter_name(*opts.name)

    # filter by flow state  -  TODO: reduce this
    if show_active and show_inactive:
        pipe |= is_active(True, filter_stop=False)
    elif show_active:
        pipe |= is_active(True)
    elif show_inactive:
        pipe |= is_active(False)

    # get contact file information
    if show_active:
        pipe |= contact_info

    graphql_fields = {}
    graphql_filters = set()

    # filter held/running flows
    if show_active and not (show_running and show_held):
        graphql_fields['status'] = None
        graphql_filters.add((('status',), tuple(opts.states)))

    # get fancy data if requested
    if formatter == _format_rich:
        # graphql_fields['status'] = None
        graphql_fields.update(RICH_FIELDS)

    # add graphql queries / filters to the pipe
    if graphql_fields:
        pipe |= graphql_query(graphql_fields, filters=graphql_filters)

    return pipe


def get_formatter(opts):
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
    else:
        raise NotImplementedError

    if opts.sort and method == _serial:
        raise ValueError(f'--sort is incompatible with --format {opts.format}')
    elif opts.sort:
        method = _sorted

    return formatter, method


async def scanner(opts):
    formatter, method = get_formatter(opts)
    pipe = get_pipe(opts, formatter)

    LOG.debug(f'pipe: {repr(pipe)}')

    await method(pipe, formatter, opts)


@cli_function(get_option_parser)
def main(parser, opts):
    # validate / standardise the list of workflow states
    opts.states = set(opts.states.split(','))
    if 'all' in opts.states:
        opts.states = FLOW_STATES
    else:
        assert opts.states
        assert all(
            state in FLOW_STATES
            for state in opts.states
        )

    # print state totals key as needed
    if opts.format == 'rich' and not opts.colour_blind:
        cprint(state_totals_keys() + '\n')

    asyncio.run(scanner(opts))
