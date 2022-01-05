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

"""Cylc univeral identifier system for referencing Cylc "objets".

This module contains the abstract ID tokenising/detokenising code.
"""

from enum import Enum
import re
from typing import (
    Dict,
    Optional,
    List,
    Tuple,
)

from cylc.flow import LOG


class Tokens(Enum):
    """Cylc object identifier tokens."""

    User = 'user'
    Workflow = 'workflow'
    Cycle = 'cycle'
    Task = 'task'
    Job = 'job'


TokensDict = Dict[str, Optional[str]]


# //cycle[:sel][/task[:sel][/job[:sel]]]
RELATIVE_PATTERN = rf'''
    //
    (?P<{Tokens.Cycle.value}>[^~\/:\n]+)
    (?:
      :
      (?P<{Tokens.Cycle.value}_sel>[^\/:\n]+)
    )?
    (?:
      /
      (?:
        (?P<{Tokens.Task.value}>[^\/:\n]+)
        (?:
          :
          (?P<{Tokens.Task.value}_sel>[^\/:\n]+)
        )?
        (?:
          /
          (?:
            (?P<{Tokens.Job.value}>[^\/:\n]+)
            (?:
              :
              (?P<{Tokens.Job.value}_sel>[^\/:\n]+)
            )?
          )?
        )?
      )?
    )?
'''

RELATIVE_ID = re.compile(
    r'^' + RELATIVE_PATTERN + r'$',
    re.X
)

# ~user[/workflow[:sel][//cycle[:sel][/task[:sel][/job[:sel]]]]]
UNIVERSAL_ID = re.compile(
    rf'''
        # don't match an empty string
        (?=.)
        # either match a user or the start of the line
        (?:
          (?:
            ~
            (?P<{Tokens.User.value}>[^\/:\n~]+)
            # allow the match to end here
            (\/|$)
          )
          |^
        )
        (?:
          (?P<{Tokens.Workflow.value}>
            # can't begin with //
            (?!//)
            # can't contain : ~ but can contain /
            [^:~\n]+?
            # can't end with /
            (?<!/)
          )
          (?:
            :
            (?P<{Tokens.Workflow.value}_sel>[^\/:\n]+)
          )?
          (?:
            (?:
                # can't end ///
                //(?!/)
            )?
            (?:
                # cycle/task/job
                { RELATIVE_PATTERN }
            )?
          )?
        )?
        $
    ''',
    re.X
)

# task.cycle[:sel]
LEGACY_TASK_DOT_CYCLE = re.compile(
    rf'''
        ^
        # NOTE: task names can contain "."
        (?P<{Tokens.Task.value}>[^~\:\/\n]+)
        \.
        # NOTE: legacy cycles always start with a number
        (?P<{Tokens.Cycle.value}>\d[^~\.\:\/\n]*)
        # NOTE: the task selector applied to the cycle in this legacy format
        # (not a mistake)
        (?:
            :
            (?P<{Tokens.Task.value}_sel>[^\:\/\n]+)
        )?
        $
    ''',
    re.X
)

# cycle/task[:sel]
LEGACY_CYCLE_SLASH_TASK = re.compile(
    rf'''
        ^
        # NOTE: legacy cycles always start with a number
        (?P<{Tokens.Cycle.value}>\d[^~\.\:\/\n]+)
        \/
        # NOTE: task names can contain "."
        (?P<{Tokens.Task.value}>[^~\:\/\n]+)
        (?:
            :
            (?P<{Tokens.Task.value}_sel>[^\:\/\n]+)
        )?
        $
    ''',
    re.X
)


def _dict_strip(dictionary):
    """Run str.strip against dictionary values.

    Examples:
        >>> _dict_strip({'a': ' x ', 'b': 'x', 'c': None})
        {'a': 'x', 'b': 'x', 'c': None}

    """
    return {
        key: value.strip() if value else None
        for key, value in dictionary.items()
    }


def legacy_tokenise(identifier: str) -> TokensDict:
    """Convert a legacy string identifier into Cylc tokens.

    Supports the two legacy Cylc7 formats:

    * task.cycle[:task_status]
    * cycle/task[:task_status]

    Args:
        identifier (str):
            The namespace to tokenise.

    Returns:
        dict - {token: value}

    Warning:
        The tokenise() function will parse a legacy token as a Workflow.

    Raises:
        ValueError:
            For invalid identifiers.

    Examples:
        # task.cycle[:task_status]
        >>> legacy_tokenise('task.123')
        {'task': 'task', 'cycle': '123', 'task_sel': None}
        >>> legacy_tokenise('task.123:task_sel')
        {'task': 'task', 'cycle': '123', 'task_sel': 'task_sel'}

        # cylc/task[:task_status]
        >>> legacy_tokenise('123/task')
        {'cycle': '123', 'task': 'task', 'task_sel': None}
        >>> legacy_tokenise('123/task:task_sel')
        {'cycle': '123', 'task': 'task', 'task_sel': 'task_sel'}

    """
    for pattern in (
        LEGACY_TASK_DOT_CYCLE,
        LEGACY_CYCLE_SLASH_TASK
    ):
        match = pattern.match(identifier)
        if match:
            return _dict_strip(match.groupdict())
    raise ValueError(f'Invalid legacy Cylc identifier: {identifier}')


def tokenise(
    identifier: str,
    relative: bool = False,
) -> TokensDict:
    """Convert a string identifier into Cylc tokens.

    Args:
        identifier (str):
            The namespace to tokenise.
        relative (bool):
            If True the prefix // is implicit if omitted.

    Returns:
        dict - {token: value}

    Warning:
        Will parse a legacy (task and or cycle) token as a Workflow.

    Raises:
        ValueError:
            For invalid identifiers.

    Examples:
        # absolute identifiers
        >>> tokenise(
        ...     '~user/workflow:workflow_sel//'
        ...     'cycle:cycle_sel/task:task_sel/job:job_sel'
        ... ) # doctest: +NORMALIZE_WHITESPACE
        {'user': 'user',
         'workflow': 'workflow',
         'workflow_sel': 'workflow_sel',
         'cycle': 'cycle',
         'cycle_sel': 'cycle_sel',
         'task': 'task',
         'task_sel': 'task_sel',
         'job': 'job',
         'job_sel': 'job_sel'}

        >>> def _(tokens):
        ...     return {
        ...         token: value for token, value in tokens.items() if value}

        # "full" identifiers
        >>> _(tokenise('workflow//cycle'))
        {'workflow': 'workflow', 'cycle': 'cycle'}

        # "partial" identifiers:
        >>> _(tokenise('~user'))
        {'user': 'user'}
        >>> _(tokenise('~user/workflow'))
        {'user': 'user', 'workflow': 'workflow'}
        >>> _(tokenise('workflow'))
        {'workflow': 'workflow'}

        # "relative" identifiers (new syntax):
        >>> _(tokenise('//cycle'))
        {'cycle': 'cycle'}
        >>> _(tokenise('cycle', relative=True))
        {'cycle': 'cycle'}
        >>> _(tokenise('//cycle/task/job'))
        {'cycle': 'cycle', 'task': 'task', 'job': 'job'}

        # whitespace stripping is employed on all values:
        >>> _(tokenise(' workflow // cycle '))
        {'workflow': 'workflow', 'cycle': 'cycle'}

        # illegal identifiers:
        >>> tokenise('a///')
        Traceback (most recent call last):
        ValueError: Invalid Cylc identifier: a///

    """
    patterns = [UNIVERSAL_ID, RELATIVE_ID]
    if relative and not identifier.startswith('//'):
        identifier = f'//{identifier}'
    for pattern in patterns:
        match = pattern.match(identifier)
        if match:
            return _dict_strip(match.groupdict())
    raise ValueError(f'Invalid Cylc identifier: {identifier}')


def detokenise(
    tokens: TokensDict,
    selectors: bool = False,
    relative: bool = False,
) -> str:
    """Convert Cylc tokens into a string identifier.

    Args:
        tokens (dict):
            Tokens as returned by tokenise.
        selectors (bool):
            If true selectors (i.e. :sel) will be included in the output.
        relative (bool):
            If true relative references are not given the `//` prefix.

    Returns:
        str - Identifier i.e. ~user/workflow//cycle/task/job

    Raises:
        ValueError:
            For invalid or empty tokens.

    Examples:
        # absolute references:
        >>> detokenise(tokenise('~user'))
        '~user'
        >>> detokenise(tokenise('~user/workflow'))
        '~user/workflow'
        >>> detokenise(tokenise('~user/workflow//cycle'))
        '~user/workflow//cycle'
        >>> detokenise(tokenise('~user/workflow//cycle/task'))
        '~user/workflow//cycle/task'
        >>> detokenise(tokenise('~user/workflow//cycle/task/4'))
        '~user/workflow//cycle/task/04'

        # relative references:
        >>> detokenise(tokenise('//cycle/task/4'))
        '//cycle/task/04'
        >>> detokenise(tokenise('//cycle/task/4'), relative=True)
        'cycle/task/04'

        # selectors are enabled using the selectors kwarg:
        >>> detokenise(tokenise('workflow:a//cycle:b/task:c/01:d'))
        'workflow//cycle/task/01'
        >>> detokenise(tokenise('workflow:a//cycle:b/task:c/01:d'), True)
        'workflow:a//cycle:b/task:c/01:d'

        # missing tokens expand to '*' (absolute):
        >>> tokens = tokenise('~user/workflow//cycle/task/01')
        >>> tokens.pop('task')
        'task'
        >>> detokenise(tokens)
        '~user/workflow//cycle/*/01'

        # missing tokens expand to '*' (relative):
        >>> tokens = tokenise('//cycle/task/01')
        >>> tokens.pop('task')
        'task'
        >>> detokenise(tokens)
        '//cycle/*/01'

        # empty tokens result in traceback:
        >>> detokenise({})
        Traceback (most recent call last):
        ValueError: No tokens provided

    """
    toks = {
        token.value
        for token in Tokens
        if tokens.get(token.value)
    }
    is_relative = not toks & {'user', 'workflow'}
    is_partial = not toks & {'cycle', 'task', 'job'}
    if is_relative and is_partial:
        raise ValueError('No tokens provided')

    for lowest_token in reversed(Tokens):
        if lowest_token.value in toks:
            break

    highest_token: 'Optional[Tokens]'
    if is_relative:
        highest_token = Tokens.Cycle
        identifier = []
        if not relative:
            identifier = ['/']
    else:
        highest_token = Tokens.User
        identifier = []

    for token in Tokens:
        if highest_token and token != highest_token:
            continue
        elif highest_token:
            highest_token = None
        value: 'Optional[str]'
        value = tokens.get(token.value)
        if not value and token == Tokens.User:
            continue
        elif token == Tokens.User:
            value = f'~{value}'
        elif token == Tokens.Job and value != 'NN':
            value = f'{int(value):02}'  # type: ignore
        value = value or '*'
        if selectors and tokens.get(token.value + '_sel'):
            # include selectors
            value = f'{value}:{tokens[token.value + "_sel"]}'
        if token == Tokens.Workflow and not is_partial:
            value += '/'
        identifier.append(value)

        if token == lowest_token:
            break

    return '/'.join(identifier)


def upgrade_legacy_ids(*ids: str) -> List[str]:
    """Reformat IDs from legacy to contemporary format:

    If no upgrading is required it returns the identifiers unchanged.

    Args:
        *ids (tuple): Identifier list.

    Returns:
        tuple/list - Identifier list.

        # do nothing to contemporary ids:
        >>> upgrade_legacy_ids('workflow')
        ['workflow']

        >>> upgrade_legacy_ids('workflow', '//cycle')
        ['workflow', '//cycle']

        # upgrade legacy task.cycle ids:
        >>> upgrade_legacy_ids('workflow', 'task.123', 'task.234')
        ['workflow', '//123/task', '//234/task']

        # upgrade legacy cycle/task ids:
        >>> upgrade_legacy_ids('workflow', '123/task', '234/task')
        ['workflow', '//123/task', '//234/task']

        # upgrade mixed legacy ids:
        >>> upgrade_legacy_ids('workflow', 'task.123', '234/task')
        ['workflow', '//123/task', '//234/task']

        # upgrade legacy task states:
        >>> upgrade_legacy_ids('workflow', 'task.123:abc', '234/task:def')
        ['workflow', '//123/task:abc', '//234/task:def']

    """
    if len(ids) < 2:
        # only legacy relative references require upgrade => abort
        return list(ids)

    legacy_ids = [ids[0]]
    for id_ in ids[1:]:
        try:
            tokens = legacy_tokenise(id_)
        except ValueError:
            # not a valid legacy token => abort
            return list(ids)
        else:
            # upgrade this token
            legacy_ids.append(
                detokenise(tokens, selectors=True)
            )

    LOG.warning(
        f'Cylc7 format is deprecated, using: {" ".join(legacy_ids)}'
        ' (see "cylc help id")'
    )
    return legacy_ids


def strip_workflow(tokens: TokensDict) -> TokensDict:
    """Remove the workflow portion of the tokens.

    Examples:
        >>> detokenise(strip_workflow(tokenise(
        ...     '~user/workflow//cycle/task/01'
        ... )))
        '//cycle/task/01'

    """
    return {
        key: value
        for key, value in tokens.items()
        if key in (
            enum.value
            for enum in (
                {*Tokens} - {Tokens.User, Tokens.Workflow}
            )
        )
    }


# TODO: rename strip_relative?
def strip_task(tokens: TokensDict) -> TokensDict:
    """Remove the task portion of the tokens.

    Examples:
        >>> detokenise(strip_task(tokenise(
        ...     '~user/workflow//cycle/task/01'
        ... )))
        '~user/workflow'

    """
    return {
        key: value
        for key, value in tokens.items()
        if key not in (
            enum.value
            for enum in (
                {*Tokens} - {Tokens.User, Tokens.Workflow}
            )
        )
    }


def strip_job(tokens: TokensDict) -> TokensDict:
    """Remove the job portion of the tokens.

    Examples:
        >>> detokenise(strip_job(tokenise('cycle/task/01', relative=True)))
        '//cycle/task'
        >>> detokenise(strip_job(tokenise(
        ...     '~user/workflow//cycle/task/01'
        ... )))
        '~user/workflow//cycle/task'

    """
    return {
        key: value
        for key, value in tokens.items()
        if key in (
            enum.value
            for enum in (
                {*Tokens} - {Tokens.Job}
            )
        )
    }


def is_null(tokens: TokensDict) -> bool:
    """Returns True if no tokens are set.

    Examples:
        >>> is_null({})
        True
        >>> is_null({'job_sel': 'x'})
        True
        >>> is_null({'job': '01'})
        False

    """
    return not any(
        bool(tokens.get(token.value))
        for token in Tokens
    )


def contains_task_like(tokens: TokensDict) -> bool:
    """Returns True if any task-like objects are present in the ID.

    Task like == cycles or tasks or jobs.

    Examples:
        >>> contains_task_like(tokenise('workflow//'))
        False
        >>> contains_task_like(tokenise('workflow//cycle'))
        True

    """
    return any(
        bool(tokens.get(token.value))
        for token in Tokens
        if token not in {Tokens.User, Tokens.Workflow}
    )


def contains_multiple_workflows(tokens_list: List[TokensDict]) -> bool:
    """Returns True if multiple workflows are contained in the tokens list.

    Examples:
        >>> a_1 = tokenise('a//1')
        >>> a_2 = tokenise('a//2')
        >>> b_1 = tokenise('b//1')

        >>> contains_multiple_workflows([a_1])
        False
        >>> contains_multiple_workflows([a_1, a_2])
        False
        >>> contains_multiple_workflows([a_1, b_1])
        True

    """
    return len({
        (tokens['user'], tokens['workflow'])
        for tokens in tokens_list
    }) > 1


def pop_token(tokens: TokensDict) -> Tuple[str, str]:
    """
        >>> tokens = tokenise('~u/w//c/t/01')
        >>> pop_token(tokens)
        ('job', '01')
        >>> pop_token(tokens)
        ('task', 't')
        >>> pop_token(tokens)
        ('cycle', 'c')
        >>> pop_token(tokens)
        ('workflow', 'w')
        >>> pop_token(tokens)
        ('user', 'u')
        >>> tokens
        {'workflow_sel': None,
         'cycle_sel': None, 'task_sel': None, 'job_sel': None}
        >>> pop_token({})
        Traceback (most recent call last):
        KeyError: No defined tokens.

    """
    for token in reversed(Tokens):
        token_name = token.value
        value = tokens.get(token_name)
        if value:
            tokens.pop(token_name)
            return (token_name, value)
    raise KeyError('No defined tokens.')


def lowest_token(tokens: TokensDict) -> str:
    """Return the lowest token present in a tokens dictionary.

    Examples:
        >>> lowest_token(tokenise('~u/w//c/t/j'))
        'job'
        >>> lowest_token(tokenise('~u/w//c/t'))
        'task'
        >>> lowest_token(tokenise('~u/w//c'))
        'cycle'
        >>> lowest_token(tokenise('~u/w//'))
        'workflow'
        >>> lowest_token(tokenise('~u'))
        'user'
        >>> lowest_token({})
        Traceback (most recent call last):
        ValueError: No tokens defined

    """
    for token in reversed(Tokens):
        if token.value in tokens and tokens[token.value]:
            return token.value
    raise ValueError('No tokens defined')
