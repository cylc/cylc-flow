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
        help='Filter flows by registered name using a regex.',
        action='append'
    )

    parser.add_option(
        '--states',
        help='List of flow states to filter by.',
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

    return parser


def make_serial(flow):
    return {
        key: str(value)
        for key, value in flow.items()
    }


def _format_json(items):
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


def _format_plain(flow):
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


def state_totals(totals):
    ret = []
    for state, tag in JOB_COLOURS.items():
        number = totals[state]
        if number == 0:
            continue
        ret.append(f'<{tag}>{number} \u25A0</{tag}>')
    return ' '.join(ret)


def _format_rich(flow):
    if not flow.get('contact'):
        ret = [f'<dim><b>{flow["name"]}</b> (stopped)</dim>']
    else:
        tag = FLOW_STATE_CMAP[flow['status']]
        ret = [
            f'<b>{flow["name"]}</b>'
            f' (<{tag}>{flow["status"]}</{tag}>)'
        ]

        display = {
            'state totals': state_totals(flow['stateTotals']),
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
        cprint(formatter(flow))


async def _serial(pipe, formatter, opts):
    ret = []
    async for item in pipe:
        ret.append(item)
    cprint(formatter(ret))


async def _async(pipe, formatter, opts):
    async for flow in pipe:
        cprint(formatter(flow))


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
    opts.states = set(opts.states.split(','))
    assert opts.states
    assert all(
        state in {'stopped', 'running', 'held'}
        for state in opts.states
    )

    asyncio.run(scanner(opts))
