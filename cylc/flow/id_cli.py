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

import asyncio
import fnmatch
from pathlib import Path
import re
from typing import Optional, Dict, List, Tuple, Any

from cylc.flow import LOG
from cylc.flow.exceptions import (
    InputError,
)
from cylc.flow.hostuserutil import get_user
from cylc.flow.id import (
    Tokens,
    contains_multiple_workflows,
    upgrade_legacy_ids,
)
from cylc.flow.pathutil import EXPLICIT_RELATIVE_PATH_REGEX
from cylc.flow.network.scan import (
    filter_name,
    is_active,
    scan,
)
from cylc.flow.workflow_files import (
    check_flow_file,
    detect_both_flow_and_suite,
    get_flow_file,
    get_workflow_run_dir,
    infer_latest_run_from_id,
    validate_workflow_name,
    abort_if_flow_file_in_path
)


FN_CHARS = re.compile(r'[\*\?\[\]\!]')


def _parse_cli(*ids: str) -> List[Tokens]:
    """Parse a list of Cylc identifiers as provided on the CLI.

    * Validates identifiers.
    * Expands relative references to absolute ones.
    * Handles legacy Cylc7 syntax.

    Args:
        *ids (tuple): Identifier list.

    Raises:
        ValueError - For invalid identifiers or identifier lists.

    Returns:
        list - List of tokens dictionaries.

    Examples:
        # parse to tokens then detokenise back
        >>> from cylc.flow.id import detokenise
        >>> parse_back = lambda *ids: list(map(detokenise, _parse_cli(*ids)))

        # list of workflows:
        >>> parse_back('workworkflow')
        ['workworkflow']
        >>> parse_back('workworkflow/')
        ['workworkflow']

        >>> parse_back('workworkflow1', 'workworkflow2')
        ['workworkflow1', 'workworkflow2']

        # absolute references
        >>> parse_back('workworkflow1//cycle1', 'workworkflow2//cycle2')
        ['workworkflow1//cycle1', 'workworkflow2//cycle2']

        # relative references:
        >>> parse_back('workworkflow', '//cycle1', '//cycle2')
        ['workworkflow//cycle1', 'workworkflow//cycle2']

        # mixed references
        >>> parse_back(
        ...     'workworkflow1', '//cycle', 'workworkflow2',
        ...     '//cycle', 'workworkflow3//cycle'
        ... )
        ['workworkflow1//cycle',
         'workworkflow2//cycle', 'workworkflow3//cycle']

        # legacy ids:
        >>> parse_back('workworkflow', 'task.123', 'a.b.c.234', '345/task')
        ['workworkflow//123/task',
         'workworkflow//234/a.b.c', 'workworkflow//345/task']

        # errors:
        >>> _parse_cli('////')
        Traceback (most recent call last):
        InputError: Invalid ID: ////

        >>> parse_back('//cycle')
        Traceback (most recent call last):
        InputError: Relative reference must follow an incomplete one.

        >>> parse_back('workflow//cycle', '//cycle')
        Traceback (most recent call last):
        InputError: Relative reference must follow an incomplete one.

        >>> parse_back('workflow///cycle/')
        Traceback (most recent call last):
        InputError: Invalid ID: workflow///cycle/

    """
    # upgrade legacy ids if required
    ids = upgrade_legacy_ids(*ids)

    partials: Optional[Tokens] = None
    partials_expended: bool = False
    tokens_list: List[Tokens] = []
    for id_ in ids:
        try:
            tokens = Tokens(id_)
        except ValueError:
            if id_.endswith('/') and not id_.endswith('//'):  # noqa: SIM106
                # tolerate IDs that end in a single slash on the CLI
                # (e.g. CLI auto completion)
                try:
                    # this ID is invalid with or without the trailing slash
                    tokens = Tokens(id_[:-1])
                except ValueError:
                    raise InputError(f'Invalid ID: {id_}')
            else:
                raise InputError(f'Invalid ID: {id_}')
        is_partial = tokens.get('workflow') and not tokens.get('cycle')
        is_relative = not tokens.get('workflow')

        if partials:
            # we previously encountered a workflow ID which did not specify a
            # cycle
            if is_partial:
                # this is an absolute ID
                if not partials_expended:
                    # no relative references were made to the previous ID
                    # so add the whole workflow to the tokens list
                    tokens_list.append(partials)
                partials = tokens
                partials_expended = False
            elif is_relative:
                # this is a relative reference => expand it using the context
                # of the partial ID
                tokens_list.append(Tokens(
                    **{
                        **partials,
                        **tokens,
                    },
                ))
                partials_expended = True
            else:
                # this is a fully expanded reference
                tokens_list.append(tokens)
                partials = None
                partials_expended = False
        else:
            # there was no previous reference that a relative reference
            # could apply to
            if is_partial:
                partials = tokens
                partials_expended = False
            elif is_relative:
                # so a relative reference is an error
                raise InputError(
                    'Relative reference must follow an incomplete one.'
                    '\nE.G: workflow //cycle/task'
                )
            else:
                tokens_list.append(tokens)

    if partials and not partials_expended:
        # if the last ID was a "partial" but not expanded add it to the list
        tokens_list.append(tokens)

    return tokens_list


def parse_ids(*args, **kwargs):
    return asyncio.run(parse_ids_async(*args, **kwargs))


async def parse_ids_async(
    *ids: str,
    src: bool = False,
    match_workflows: bool = False,
    match_active: Optional[bool] = True,
    infer_latest_runs: bool = True,
    constraint: str = 'tasks',
    max_workflows: Optional[int] = None,
    max_tasks: Optional[int] = None,
    alt_run_dir: Optional[str] = None,
) -> Tuple[Dict[str, List[Tokens]], Any]:
    """Parse IDs from the command line.

    Args:
        ids:
            Collection of IDs to parse.
        src:
            If True then source workflows can be provided via an absolute
            path or a relative path starting "./".
            Infers max_workflows = 1.
        match_workflows:
            If True workflows can be globs.
        match_active:
            If match_workflows is True this determines the wokflow state
            filter.

            True - running & paused
            False - stopped
            None - any
        infer_latest_runs:
            If true infer the latest run for a workflow when applicable
            (allows 'cylc play one' rather than 'cylc play one/run1').
        constraint:
            Constrain the types of objects the IDs should relate to.

            workflows - only allow workflows.
            tasks - require tasks to be defined.
            mixed - permit tasks not to be defined.
        max_workflows:
            Specify the maximum number of workflows permitted to be specified
            in the ids.
        max_tasks:
            Specify the maximum number of tasks permitted to be specified
            in the ids.

    Returns:
        With src=True":
            (workflows, flow_file_path)
        Else:
            (workflow, multi_mode)
        Where:
            workflows:
                Dictionary containing workflow ID strings against lists of
                relative tokens specified on that workflow.
                {workflow_id: [relative_tokens]}
            flow_file_path:
                Path to the flow.cylc (or suite.rc in Cylc 7 compat mode)
            multi_mode:
                True if multiple workflows selected or if globs were provided
                in the IDs.

    """
    if constraint not in {'tasks', 'workflows', 'mixed'}:
        raise ValueError(f'Invalid constraint: {constraint}')

    tokens_list = []
    src_path = None
    flow_file_path = None
    multi_mode = False

    if src:
        # can only have one workflow if permitting source workflows
        max_workflows = 1
        ret = _parse_src_path(ids[0])
        if ret:
            # yes, replace the path with an ID and continue
            workflow_id, src_path, flow_file_path = ret
            ids = (
                Tokens(
                    user=None,
                    workflow=workflow_id,
                ).id + '//',
                *ids[1:]
            )
    tokens_list.extend(_parse_cli(*ids))

    # ensure the IDS are compatible with the constraint
    _validate_constraint(*tokens_list, constraint=constraint)

    if match_workflows:
        # match workflow IDs via cylc-scan
        # if any patterns are present switch to multi_mode for clarity
        multi_mode = await _expand_workflow_tokens(
            tokens_list,
            match_active=match_active,
        )

    # check the workflow part of the IDs are valid
    _validate_workflow_ids(*tokens_list, src_path=src_path)

    if not multi_mode:
        # check how many workflows we are working on
        multi_mode = contains_multiple_workflows(tokens_list)

    # infer the run number if not specified the ID (and if possible)
    if infer_latest_runs:
        _infer_latest_runs(
            *tokens_list, src_path=src_path, alt_run_dir=alt_run_dir)

    _validate_number(
        *tokens_list,
        max_workflows=max_workflows,
        max_tasks=max_tasks,
    )

    workflows = _batch_tokens_by_workflow(*tokens_list, constraint=constraint)

    if src:
        if not flow_file_path:
            # get the workflow file path from the run dir
            flow_file_path = get_flow_file(list(workflows)[0])
        return workflows, flow_file_path
    return workflows, multi_mode


def parse_id(*args, **kwargs) -> Tuple[str, Optional[Tokens], Any]:
    return asyncio.run(parse_id_async(*args, **kwargs))


async def parse_id_async(
    *args,
    **kwargs,
) -> Tuple[str, Optional[Tokens], Any]:
    """Special case of parse_ids with a more convenient return format.

    Infers:
        max_workflows: 1
        max_tasks: 1

    """
    workflows, ret = await parse_ids_async(
        *args,
        **{  # type: ignore
            **kwargs,
            'max_workflows': 1,
            'max_tasks': 1,
        },
    )
    workflow_id = list(workflows)[0]
    tokens_list = workflows[workflow_id]
    tokens: Optional[Tokens]
    if tokens_list:
        tokens = tokens_list[0]
    else:
        tokens = None
    return workflow_id, tokens, ret


def contains_fnmatch(string: str) -> bool:
    """Return True if a string contains filename match chars.

    Examples:
        >>> contains_fnmatch('a')
        False
        >>> contains_fnmatch('*')
        True
        >>> contains_fnmatch('abc')
        False
        >>> contains_fnmatch('a*c')
        True
    """
    return bool(FN_CHARS.search(string))


def _validate_constraint(*tokens_list, constraint=None):
    if constraint == 'workflows':
        for tokens in tokens_list:
            if tokens.is_null or tokens.is_task_like:
                raise InputError('IDs must be workflows')
        return
    if constraint == 'tasks':
        for tokens in tokens_list:
            if tokens.is_null or not tokens.is_task_like:
                raise InputError('IDs must be tasks')
        return
    if constraint == 'mixed':
        for tokens in tokens_list:
            if tokens.is_null:
                raise InputError('IDs cannot be null.')
        return


def _validate_workflow_ids(*tokens_list, src_path):
    for ind, tokens in enumerate(tokens_list):
        if tokens['user'] and (tokens['user'] != get_user()):
            raise InputError(
                "Operating on other users' workflows is not supported"
            )
        if not src_path:
            validate_workflow_name(tokens['workflow'])
        if ind == 0 and src_path:
            # source workflow passed in as a path
            pass
        else:
            src_path = Path(get_workflow_run_dir(tokens['workflow']))
        if src_path.is_file():
            raise InputError(
                f'Workflow ID cannot be a file: {tokens["workflow"]}'
            )
        if tokens['cycle'] and tokens['cycle'].startswith('run'):
            # issue a warning if the run number is provided after the //
            # separator e.g. workflow//run1 rather than workflow/run1//
            suggested = Tokens(
                user=tokens['user'],
                workflow=f'{tokens["workflow"]}/{tokens["cycle"]}',
                cycle=tokens['task'],
                task=tokens['job'],
            )
            LOG.warning(f'Did you mean: {suggested.id}')
        detect_both_flow_and_suite(src_path)


def _infer_latest_runs(*tokens_list, src_path, alt_run_dir=None):
    for ind, tokens in enumerate(tokens_list):
        if ind == 0 and src_path:
            # source workflow passed in as a path
            continue
        tokens['workflow'] = infer_latest_run_from_id(
            tokens['workflow'], alt_run_dir)
        pass


def _validate_number(*tokens_list, max_workflows=None, max_tasks=None):
    if not max_workflows and not max_tasks:
        return
    workflows_count = 0
    tasks_count = 0
    for tokens in tokens_list:
        if tokens.is_task_like:
            tasks_count += 1
        else:
            workflows_count += 1
    if max_workflows and workflows_count > max_workflows:
        raise InputError(
            f'IDs contain too many workflows (max {max_workflows})'
        )
    if max_tasks and tasks_count > max_tasks:
        raise InputError(
            f'IDs contain too many cycles/tasks/jobs (max {max_tasks})'
        )


def _batch_tokens_by_workflow(*tokens_list, constraint=None):
    """Sorts tokens into lists by workflow ID.

    Example:
        >>> _batch_tokens_by_workflow(
        ...     Tokens(workflow='x', cycle='1'),
        ...     Tokens(workflow='x', cycle='2'),
        ... )
        {'x': [<id: //1>, <id: //2>]}

    """
    workflow_tokens = {}
    for tokens in tokens_list:
        w_tokens = workflow_tokens.setdefault(tokens['workflow'], [])
        relative_tokens = tokens.task
        if constraint in {'mixed', 'workflows'} and relative_tokens.is_null:
            continue
        w_tokens.append(relative_tokens)
    return workflow_tokens


async def _expand_workflow_tokens(tokens_list, match_active=True):
    multi_mode = False
    for tokens in list(tokens_list):
        workflow = tokens['workflow']
        if not contains_fnmatch(workflow):
            # no expansion to perform
            continue
        else:
            # remove the original entry
            multi_mode = True
            tokens_list.remove(tokens)
            async for tokens in _expand_workflow_tokens_impl(
                tokens,
                match_active=match_active,
            ):
                # add the expanded tokens back onto the list
                tokens_list.append(tokens)
    return multi_mode


async def _expand_workflow_tokens_impl(tokens, match_active=True):
    """Use "cylc scan" to expand workflow patterns."""
    workflow_sel = tokens['workflow_sel']
    if workflow_sel and workflow_sel != 'running':
        raise InputError(
            f'The workflow selector :{workflow_sel} is not'
            'currently supported.'
        )

    # construct the pipe
    pipe = scan | filter_name(fnmatch.translate(tokens['workflow']))
    if match_active is not None:
        pipe |= is_active(match_active)

    # iter the results
    async for workflow in pipe:
        yield tokens.duplicate(workflow=workflow['name'])


def _parse_src_path(id_):
    """Parse CLI workflow arg to find a valid source directory.

    Returns:
      - (dir name, dir path, config file path) if id_ is a valid src dir.
      - or None, if id_ could be a workflow ID

    A valid source directory is:
      - an existing directory that contains a worklow config file
    and not a relative path (which could be a workflow ID), i.e. it must be:
      - the current directory (".")
      - or a directory path that starts with "./"
      - or an absolute directory path

    It's OK if id_ happens to match a relative path to an existing directory or
    file (other than a workflow config file) because there could be a workflow
    ID with the same name.

    """
    abort_if_flow_file_in_path(Path(id_))
    src_path = Path(id_)
    if (
        not EXPLICIT_RELATIVE_PATH_REGEX.match(id_)
        and not src_path.is_absolute()
    ):
        # Not a valid source path, but it could be a workflow ID.
        return None

    src_dir_path = src_path.resolve()
    if not src_dir_path.exists():
        raise InputError(f'Source directory not found: {src_dir_path}')

    if not src_dir_path.is_dir():
        raise InputError(f'Path is not a source directory: {src_dir_path}')

    src_file_path = check_flow_file(src_dir_path)

    return src_dir_path.name, src_dir_path, src_file_path
