#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

"""cylc completion-server [OPTIONS]

A server for providing Cylc CLI completion results.

This server accepts requests containing the command line and returns responses
containing possible completions for the last word on the command line.

See `cylc get-resources` for available completion scripts using this server.
"""

# NOTE: Developers
#
# This server is launched automatically in the user's shell. If it dies it
# gets restarted. It's important to handle error cases very carefully as
# we don't want these servers getting caught in crash/restart loops or causing
# hassle to users.
#
# This file contains:
# * Completion functions:
#   Which "complete" words e.g. 'a' might match 'a1', 'a2' but not 'b1'.
# * Listing functions:
#   Which provide possible values to the completion functions.

import asyncio
import os
from pathlib import Path
import select
import sys
import typing as t

from pkg_resources import (
    parse_requirements,
    parse_version
)

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.id import tokenise, IDTokens, Tokens
from cylc.flow.network.scan import scan
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import get_workflow_run_job_dir
from cylc.flow.resources import (
    list_resources as list_resources_,
    RESOURCE_DIR,
)
from cylc.flow.scripts.cylc import COMMANDS
from cylc.flow.scripts.scan import FLOW_STATES, get_pipe, ScanOptions
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import infer_latest_run_from_id

if t.TYPE_CHECKING:
    from optparse import Values

# do not list this command in `cylc help all` output
INTERNAL = True

# set the compatibility range for completion scripts with this server
# I.E. if we change the server interface, change this compatibility range.
# User's will be presented with an upgrade notice if this happens.
REQUIRED_SCRIPT_VERSION = 'completion-script >=1.0.0, <2.0.0'

# register the psudo "help" and "version" commands
COMMAND_LIST = list(COMMANDS) + ['help', 'version']


def stdin(timeout: int = 2) -> t.Iterator[str]:
    """Yield lines from stdin, stop on configured read timeout.

    Args:
        timeout:
            Read timeout in seconds, if no new input is received within this
            period the generator will exit.

    Yields:
        The file line by line.

    """
    while True:
        if select.select([sys.stdin], [], [], timeout)[0]:
            # wait for input => yield
            yield sys.stdin.readline()
        else:
            # timeout => stop iterating
            return


async def server(
    listener: t.Callable,
    responder: t.Callable,
    once: bool = False,
    write: t.Callable[[str], None] = print,
    timeout: int = 60,
) -> None:
    """The bit that handles incoming requests.

    * Accepts requests in the format `cylc|trigger|workfl`.
    * Writes responses in the format cylc trigger workflow//`.

    Args:
        listener:
            Generator function which yields requests.
            Must accept a `timeout` (seconds) argument.
        responder:
            Function which yields a list of possible responses.
            responder(commandline: List[str]) => List[str].
        once:
            Return after sending the first response.
        write:
            The function which sends the response back to the originator.
        timeout:
            Max time to wait for new requests.

    Note:
        The server will not play nicely with completions which contain spaces
        (they will show as separate completions).

        Completions should not contain spaces, workflows/cycles/tasks/jobs
        cannot contain spaces (due to validation rules) so this is ok.

    """
    for line in listener(timeout=timeout):
        try:
            write(' '.join(
                item
                for item in sorted(await responder(*line[:-1].split('|')))
            ))
        except Exception:
            # catch everything! If an error occurs swallow it, we don't want
            # it to reach the CLI or to cause the server to get caught in
            # a crash/restart loop
            write('')  # send an empty reply
        if once:
            return
        sys.stdout.flush()


async def complete_cylc(_root: str, *items: str) -> t.List[str]:
    """Return Cylc CLI completions for the provided args.

    Args:
        _root:
            The root command i.e. `cylc`.
        items:
            The command items e.g. ['trigger', 'workfl']

    Returns:
        List of possible completions e.g. ['workflow_a//', 'workflow_b//']

    """
    length: int = len(items)

    # the word to complete
    partial: t.Optional[str] = None
    if length > 0:
        partial = items[-1]

    # the previous word
    previous: t.Optional[str] = None
    if length > 1:
        previous = items[-2]

    # complete the cylc sub-command
    if length == 0:
        return await complete_command()
    if length == 1:
        return await complete_command(partial)
    command: str = items[0]

    # special logic for the pseudo "help" and "version" commands
    if command == 'help':
        return complete(partial, ['id', 'all'])
    if command == 'version':
        return complete(partial, ['--long'])

    # complete --options
    if partial and partial.startswith('-'):
        ret = await complete_option(command, partial)
        if ret is not None:
            return ret
    if previous and previous.startswith('-'):
        ret = await complete_option_value(command, previous, partial)
        if ret is not None:
            return ret

    # complete positional arguments
    return await complete_argument(command, partial)


def complete(
    partial: t.Optional[str],
    words: t.Iterable[str]
) -> t.List[str]:
    """Return only matching words.

    Args:
        partial:
            The string to match.
        words:
            The list of words to match against.

    Returns:
        The filtered list of matching words.

    Examples:
        >>> complete('w', ['beans', 'walrus', 'wellington'])
        ['walrus', 'wellington']

    """
    if partial is None:
        return list(words)
    return [
        word
        for word in words
        if word.startswith(partial)
    ]


async def complete_command(partial: str = None) -> t.List[str]:
    """Complete Cylc commands."""
    return complete(partial, COMMAND_LIST)


async def complete_option(
    command: str,
    partial: str = None
) -> t.Optional[t.List[str]]:
    """Complete --options."""
    if partial and '=' in partial:
        option, partial = partial.split('=', 1)
        values = await complete_option_value(command, option, partial)
        if values is None:
            return None
        return [  # filtering already performed by complete_option_value
            f'{option}={value}'
            for value in values
        ]

    return complete(partial, list_options(command))


async def complete_option_value(
    command: str,
    option: str,
    partial: t.Optional[str] = None
) -> t.Optional[t.List[str]]:
    """Complete values for --options."""
    vals = await list_option_values(command, option, partial)
    if vals is not None:
        return complete(partial, vals)
    return None


async def complete_argument(
    command: str,
    partial: t.Optional[str] = None,
) -> t.List[str]:
    """Complete arguments for commands."""
    coro = COMMAND_MAP.get(command, list_cylc_id)
    if coro is None:
        # argument completion disabled for this command
        return []
    return complete(
        partial,
        await coro(partial),
    )


async def list_cylc_id(partial: str) -> t.List[str]:
    """List Cylc IDs (workflows//cycles/tasks/jobs)."""
    partial = partial or ''

    try:
        tokens = tokenise(partial)
    except ValueError:
        tokens = Tokens()

    # strip off any partial IDs
    # e.g. workflow//12      => workflow//
    # e.g. workflow//1234/ta => workflow//1234
    if not partial.endswith('/') and not tokens.is_null:
        tokens.pop_token()

    if tokens.is_null:
        # if there are no tokens, list all workflows
        ids = await list_workflows()
    else:
        # if there are tokens, list things within that workflow
        ids = await list_in_workflow(tokens)

    return ids


def list_options(command: str) -> t.List[str]:
    """List CLI options from a Cylc command.

    E.G. ['--help', '--debug', '--color', ....]

    Note: This provides the long formats of options e.g. `--help` not `-h`.
    """
    try:
        entry_point = COMMANDS[command].resolve()
    except KeyError:
        return []
    parser = entry_point.parser_function()
    if getattr(parser, 'auto_add', None):
        parser.add_std_options()
    return [
        option.get_opt_string()
        for option in parser.option_list
    ]


async def list_option_values(
    command: str,
    option: str,
    partial: t.Optional[str] = '',
) -> t.Optional[t.List[str]]:
    """List values for an option in a Cylc command.

    E.G. --flow ['all', 'new', 'none']
    """
    if option in OPTION_MAP:
        list_option = OPTION_MAP[option]
        if not list_option:
            # do not perform completion for this option
            return []
        return await list_option(None, partial)
    return None


async def list_workflows(states: t.Set[str] = None) -> t.List[str]:
    """List workflows from run directories."""
    pipe = get_pipe(ScanOptions(states=states or FLOW_STATES), 'None')
    ids = []
    async for flow in pipe:
        ids.append(cli_detokenise(Tokens(workflow=flow['name'])))
    return ids


async def list_src_workflows(_partial: str) -> t.List[str]:
    """List workflow source directories from "source dirs"."""
    ret = []
    for src_dir in glbl_cfg().get(['install', 'source dirs']):
        async for src_flow in scan(run_dir=Path(src_dir).expanduser()):
            ret.append(src_flow['name'])
    return ret


async def list_in_workflow(tokens: Tokens, infer_run=True) -> t.List[str]:
    """List cycles/tasks/jobs from within a workflow."""
    if not tokens.get('workflow'):
        return []
    parts = []
    if tokens.get('cycle'):
        parts.append(tokens['cycle'])
    if tokens.get('task'):
        parts.append(tokens['task'])
    if tokens.get('job'):
        parts.append(tokens['job'])
    input_workflow = tokens['workflow']  # workflow ID as provided on the CLI
    if infer_run:
        # workflow ID after run name inference
        inferred_workflow = infer_latest_run_from_id(input_workflow)
    else:
        inferred_workflow = input_workflow
    job_dir = Path(get_workflow_run_job_dir(inferred_workflow, *parts))
    if not job_dir.exists():
        # no job dir (e.g. workflow has not been run yet)
        return []
    token = next_token(tokens)
    if token:
        return [
            # list possible IDs
            cli_detokenise(
                tokens.duplicate(
                    tokens=None,
                    # use the workflow ID provided on the CLI to allow
                    # run name inference
                    workflow=input_workflow,
                    **{token: path.name},
                )
            )
            for path in job_dir.iterdir()
        ]
    return []


async def list_resources(_partial: str) -> t.List[str]:
    """Return the list of resources accessible through cylc get-resources."""
    resources: t.List[str] = []
    list_resources_(resources.append, headers=False)
    return [
        resource.split('#')[0].strip()
        for resource in resources
    ]


async def list_dir(
    _workflow: t.Optional[str],
    partial: t.Optional[str]
) -> t.List[str]:
    """List an arbitrary dir on the filesystem.

    Relative dirs are assumed relative to `$PWD`.
    """
    if partial:
        path = Path(partial)
        if not partial.endswith('/'):
            path = path.parent
        if path.is_absolute():
            return list_abs_dir(path)
        return list_rel_dir(path, Path('.'))

    return list_rel_dir(Path('.'), Path('.'))


def list_abs_dir(path: Path) -> t.List[str]:
    """List an absolute directory."""
    if not path.is_dir():
        return [str(path)]
    return [
        f'{sub_path}/' if sub_path.is_dir() else str(sub_path)
        for sub_path in path.iterdir()
    ]


def list_rel_dir(path: Path, base: Path) -> t.List[str]:
    """List a relative directory.

    Args:
        path: The directory to list.
        base: Results are given relative to this.

    """
    if not path.is_dir():
        return [str(path)]
    return [
        f'{sub_path.relative_to(base)}/'
        if sub_path.is_dir()
        else str(sub_path.relative_to(base))
        for sub_path in path.iterdir()
    ]


async def list_flows(
    _workflow: t.Optional[str],
    _partial: t.Optional[str]
) -> t.List[str]:
    """List values for the --flow option."""
    return ['all', 'none', 'new']


async def list_colours(
    _workflow: t.Optional[str],
    _partial: t.Optional[str]
) -> t.List[str]:
    """List values for the --color option."""
    return ['never', 'auto', 'always']


# non-exhaustive list of Cylc commands which take non-workflow arguments
COMMAND_MAP: t.Dict[str, t.Optional[t.Callable]] = {
    # register commands which have special positional arguments
    'install': list_src_workflows,
    'get-resources': list_resources,
    # commands for which we should not attempt to complete arguments
    'scan': None,
    'cycle-point': None,
    'message': None,
}

# non-exhaustive list of Cylc CLI options
# (the ideal solution would inspect the meta-variables for each option)
OPTION_MAP: t.Dict[str, t.Optional[t.Callable]] = {
    # register --options which need special treatment
    '--set-file': list_dir,
    '--file': list_dir,
    '--output': list_dir,
    '--flow': list_flows,
    '--colour': list_colours,
    '--color': list_colours,
    # options for which we should not attempt to complete values for
    '--rm': None,
    '--run-name': None,
    '--initial-cycle-point': None,
    '--final-cycle-point': None,
    '--start-cycle-point': None,
    '--stop-cycle-point': None,
    '--start-task': None,
    '--hold-cycle-point': None,
    '--host': None,
    '--format': None,
    '--main-loop': None,
}


def cli_detokenise(tokens: Tokens) -> str:
    """Format tokens for use on the command line.

    I.E. add the trailing slash[es] onto the end.
    """
    if tokens.is_null:
        # shouldn't happen but prevents possible error
        return ''
    if tokens.lowest_token == IDTokens.Workflow.value:
        return f'{tokens.id}//'
    return f'{tokens.id}/'


def next_token(tokens: Tokens) -> t.Optional[str]:
    """Return the first unspecified token.

    Examples:
        >>> next_token(Tokens())
        'workflow'
        >>> next_token(Tokens(workflow='a'))
        'cycle'
        >>> next_token(Tokens(workflow='a', cycle='1'))
        'task'
        >>> next_token(Tokens(workflow='a', cycle='1', task='x'))
        'job'
        >>> next_token(Tokens(workflow='a', cycle='1', task='x', job='01'))

    """
    if tokens.is_null:
        return IDTokens.Workflow.value
    lowest_token = IDTokens(tokens.lowest_token)
    next_ = False
    for token in IDTokens:
        if next_:
            return token.value
        if token == lowest_token:
            next_ = True
    return None


def get_completion_script_file(completion_lang: str) -> t.Optional[Path]:
    """Return the path of the completion script for the specified language.

    Returns None if there is no completion script for the provided language.
    """
    completion_script = (RESOURCE_DIR / f'cylc-completion.{completion_lang}')
    if not completion_script.exists():
        return None
    return completion_script


def get_current_completion_script_version(
    completion_script: Path,
    completion_lang: str,
) -> t.Optional[str]:
    """Extract the script version from the provided script.

    Returns None if the script version cannot be determined.
    """
    if completion_lang == 'bash':
        with open(completion_script, 'r') as script:
            for line in script:
                if line.startswith('export CYLC_COMPLETION_SCRIPT_VERSION='):
                    return line.replace(
                        'export CYLC_COMPLETION_SCRIPT_VERSION=',
                        ''
                    )
    return None


def check_completion_script_compatibility(
    completion_lang: str,
    completion_script_version: str,
) -> bool:
    """Check if a completion script is compatible with this server.

    Prints upgrade advice to `sys.stderr` as appropriate.

    Args:
        completion_lang:
            The language the completion script is implemented for e.g. `Bash`.
        completion_script_version:
            The completion script version e.g. `1.0.0`.

    Returns:
        True if the completion script is compatible, else False.

    """
    is_compatible = True

    # get the version of the completion script bundled with this version of
    # Cylc
    completion_script = get_completion_script_file(completion_lang)
    if completion_script is None:
        return False
    current_version = get_current_completion_script_version(
        completion_script,
        completion_lang,
    )
    if current_version is None:
        return True

    current_version = parse_version(current_version)
    installed_version = parse_version(completion_script_version)

    # check that the installed completion script is compabile with this
    # completion server version
    for requirement in parse_requirements(REQUIRED_SCRIPT_VERSION):
        # NOTE: there's only one requirement but we have to iterate to get it
        if installed_version not in requirement:
            is_compatible = False
            print(
                f'The Cylc {completion_lang} script needs to be updated to'
                ' work with this version of Cylc.',
                file=sys.stderr,
            )

    # check for completion script updates
    if installed_version < current_version:
        print(
            f'A new version of the Cylc {completion_lang} script is available.'
            f'\nGet it with: cylc get-resources {completion_script.name} PATH',
            file=sys.stderr,
        )

    return is_compatible


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
    )

    parser.add_option(
        '--timeout',
        type='int',
        default='300',
        help=(
            'The maximum idle time before the server shuts down in seconds.'
        )
    )

    parser.add_option(
        '--once',
        action='store_true',
        default=False,
        help=(
            'Exit after returning the first response (for testing purposes).'
        )
    )

    return parser


@cli_function(get_option_parser)
def main(_, opts: 'Values') -> None:
    completion_lang = os.environ.get('CYLC_COMPLETION_LANG')
    completion_script_version = os.environ.get(
        'CYLC_COMPLETION_SCRIPT_VERSION'
    )

    if (
        # if we are being called by a completion script, check the script
        # is compatible with this server version before proceeding
        completion_lang
        and completion_script_version
        and not check_completion_script_compatibility(
            completion_lang,
            completion_script_version,
        )
    ):
        # this server version is not compatible with the script version
        return

    asyncio.run(
        server(
            stdin,
            complete_cylc,
            once=opts.once,
            timeout=opts.timeout
        )
    )
