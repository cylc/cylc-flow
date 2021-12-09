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

from cylc.flow import LOG
from cylc.flow.exceptions import UserInputError


class Tokens(Enum):
    """Cylc object identifier tokens."""

    User = 'user'
    Workflow = 'workflow'
    Cycle = 'cycle'
    Task = 'task'
    Job = 'job'


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
          (?P<{Tokens.Workflow.value}>[^\/:\n~]+)
          (?:
            :
            (?P<{Tokens.Workflow.value}_sel>[^\/:\n]+)
          )?
          (?:
            (?:
                //
            )?
            (?:

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
        (?P<{Tokens.Cycle.value}>\d[^~\.\:\/\n]+)
        # NOTE: the task selector applied to the cycle in this legacy format
        # (note a mistake)
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


def legacy_tokenise(identifier):
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


def tokenise(identifier):
    """Convert a string identifier into Cylc tokens.

    Args:
        identifier (str):
            The namespace to tokenise.

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
    for pattern in patterns:
        match = pattern.match(identifier)
        if match:
            return _dict_strip(match.groupdict())
    raise ValueError(f'Invalid Cylc identifier: {identifier}')


def detokenise(tokens, selectors=False, relative=False):
    """Convert Cylc tokens into a string identifier.

    Args:
        tokens (dict):
            Tokens as returned by tokenise.
        selectors (bool):
            If true selectors (i.e. :sel) will be included in the output.
        relative (bool):
            If true relative references are not given the `//` prefix.
            TODO: remove this?

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
        value = tokens.get(token.value)
        if not value and token == Tokens.User:
            continue
        elif token == Tokens.User:
            value = f'~{value}'
        elif token == Tokens.Job and value != 'NN':
            value = f'{int(value):02}'
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


def upgrade_legacy_ids(*ids):
    """Reformat IDs from legacy to contemporary format:

    If no upgrading is required it returns the identifiers unchanged.

    Args:
        *ids (tuple): Identifier list.

    Returns:
        tuple/list - Identifier list.

        # do nothing to contemporary ids:
        >>> upgrade_legacy_ids('workflow')
        ('workflow',)

        >>> upgrade_legacy_ids('workflow', '//cycle')
        ('workflow', '//cycle')

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
        return ids

    legacy_ids = [ids[0]]
    for id_ in ids[1:]:
        try:
            tokens = legacy_tokenise(id_)
        except ValueError:
            # not a valid legacy token => abort
            return ids
        else:
            # upgrade this token
            legacy_ids.append(
                detokenise(tokens, selectors=True)
            )

    LOG.warning(
        f'Cylc7 format is deprecated using: {" ".join(legacy_ids)}'
    )
    return legacy_ids


def strip_workflow(tokens):
    """Remove the workflow portion of the tokens.

    Examples:
        >>> detokenise(strip_workflow(tokenise(
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


def strip_task(tokens):
    """Remove the task portion of the tokens.

    Examples:
        >>> detokenise(strip_task(tokenise(
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


def is_null(tokens):
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


def contains_task_like(tokens):
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


def contains_multiple_workflows(tokens_list):
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


def pop_token(tokens):
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
        {'workflow_sel': None, 'cycle_sel': None, 'task_sel': None, 'job_sel': None}

    """
    for token_name in reversed(Tokens):
        token_name = token_name.value
        if token_name in tokens and tokens[token_name]:
            return (token_name, tokens.pop(token_name))


def parse_cli(*ids):
    # TOOD move?
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
        >>> parse_back = lambda *ids: list(map(detokenise, parse_cli(*ids)))

        # list of workflows:
        >>> parse_back('workworkflow')
        ['workworkflow']

        >>> parse_back('workworkflow1', 'workworkflow2')
        ['workworkflow1', 'workworkflow2']

        # sbsolute references
        >>> parse_back('workworkflow1//cycle1', 'workworkflow2//cycle2')
        ['workworkflow1//cycle1', 'workworkflow2//cycle2']

        # relative references:
        >>> parse_back('workworkflow', '//cycle1', '//cycle2')
        ['workworkflow//cycle1', 'workworkflow//cycle2']

        # mixed references
        >>> parse_back('workworkflow1', '//cycle', 'workworkflow2', '//cycle', 'workworkflow3//cycle')
        ['workworkflow1//cycle', 'workworkflow2//cycle', 'workworkflow3//cycle']

        # legacy ids:
        >>> parse_back('workworkflow', 'task.123', 'a.b.c.234', '345/task')
        ['workworkflow//123/task', 'workworkflow//234/a.b.c', 'workworkflow//345/task']

        # errors:
        >>> parse_cli('////')
        Traceback (most recent call last):
        ValueError: Invalid Cylc identifier: ////

        >>> parse_back('//cycle')
        Traceback (most recent call last):
        ValueError: Relative reference must follow an incomplete one.
        E.G: workflow //cycle/task

        >>> parse_back('workflow//cycle', '//cycle')
        Traceback (most recent call last):
        ValueError: Relative reference must follow an incomplete one.
        E.G: workflow //cycle/task

    """
    # upgrade legacy ids if required
    ids = upgrade_legacy_ids(*ids)

    partials = None
    partials_expended = False
    tokens_list = []
    for id_ in ids:
        tokens = tokenise(id_)
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
                tokens_list.append({
                    **partials,
                    **tokens
                })
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
                raise ValueError(
                    'Relative reference must follow an incomplete one.'
                    '\nE.G: workflow //cycle/task'
                )
            else:
                tokens_list.append(tokens)

    if partials and not partials_expended:
        # if the last ID was a "partial" but not expanded add it to the list
        tokens_list.append(tokens)

    return tokens_list


def parse_ids(*ids):
    tokens_list = parse_cli(*ids)
    workflows = {}
    for tokens in tokens_list:
        if tokens['user']:
            # TODO
            raise UserInputError('Changing user not supported')
        if tokens['workflow_sel']:
            raise UserInputError('Selectors cannot be used on workflows')
        key = tokens['workflow']
        workflows.setdefault(key, []).append(
            detokenise(strip_workflow(tokens), relative=True)
        )
    return workflows


def parse_id(id_, src=False):
    return parse_cli(id_)[0]
