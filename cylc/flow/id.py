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

"""Cylc univeral identifier system for referencing Cylc "objects".

This module contains the abstract ID tokenising/detokenising code.
"""

from enum import Enum
import re
from typing import (
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from cylc.flow import LOG


class IDTokens(Enum):
    """Cylc object identifier tokens."""

    User = 'user'
    Workflow = 'workflow'
    Cycle = 'cycle'
    Task = 'task'
    Job = 'job'


class Tokens(dict):
    """A parsed representation of a Cylc universal identifier (UID).

    Examples:
        Parse tokens:
        >>> tokens = Tokens('~u/w//c/t/01')
        >>> tokens
        <id: ~u/w//c/t/01>

        Parse back to a string ID:
        >>> tokens.id
        '~u/w//c/t/01'
        >>> tokens.workflow_id
        '~u/w'
        >>> tokens.relative_id
        'c/t/01'

        Inspect the tokens:
        >>> tokens['user']
        'u'
        >>> tokens['task']
        't'
        >>> tokens['task_sel']  # task selector
        >>> list(tokens.values())  # Note the None values are selectors
        ['u', 'w', None, 'c', None, 't', None, '01', None]

        Construct tokens:
        >>> Tokens(workflow='w', cycle='c')
        <id: w//c>
        >>> Tokens(workflow='w', cycle='c')['job']

        # Make a copy (note Tokens are mutable):
        >>> tokens.duplicate()
        <id: ~u/w//c/t/01>
        >>> tokens.duplicate(job='02')  # make changes at the same time
        <id: ~u/w//c/t/02>

    """
    _REGULAR_KEYS: Set[str] = {token.value for token in IDTokens}
    _SELECTOR_KEYS = {
        f'{token.value}_sel'
        for token in IDTokens
        if token != IDTokens.User
    }

    # all valid dictionary keys
    _KEYS = _REGULAR_KEYS | _SELECTOR_KEYS

    _TASK_LIKE_KEYS = {
        key for key in _KEYS if not (
            key.startswith(IDTokens.User.value)
            or key.startswith(IDTokens.Workflow.value)
        )
    }

    def __init__(
        self,
        *args: 'Union[str, Tokens]',
        relative: bool = False,
        **kwargs: Optional[str]
    ):
        if args:
            if len(args) > 1:
                raise ValueError()
            if isinstance(args[0], str):
                kwargs = tokenise(str(args[0]), relative)
            else:
                kwargs = dict(args[0])
        else:
            for key in kwargs:
                if key not in self._KEYS:
                    raise ValueError(f'Invalid token: {key}')
        dict.__init__(self, **kwargs)

    def __setitem__(self, key, value):
        if key not in self._KEYS:
            raise ValueError(f'Invalid token: {key}')
        dict.__setitem__(self, key, value)

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            if key not in self._KEYS:
                raise ValueError(f'Invalid token: {key}')
            return None

    def __str__(self):
        return self.id

    def __repr__(self):
        """Python internal representation.

        Examples:
            >>> Tokens('a//1')
            <id: a//1>
            >>> Tokens('//1', relative=True)
            <id: //1>
            >>> Tokens()
            <id: >

        """
        if self.is_null:
            id_ = ''
        else:
            id_ = self.id
        return f'<id: {id_}>'

    def __eq__(self, other):
        return all(
            self[key] == other[key]
            for key in self._KEYS
        )

    def __ne__(self, other):
        return any(
            self[key] != other[key]
            for key in self._KEYS
        )

    @property # noqa A003 (not shadowing id built-in)
    def id(self) -> str:  # noqa A003 (not shadowing id built-in)
        """The full ID these tokens represent.

        Examples:
            >>> Tokens('~u/w//c/t/01').id
            '~u/w//c/t/01'
            >>> Tokens().id
            Traceback (most recent call last):
            ValueError: No tokens provided

        """
        return detokenise(self)

    @property
    def relative_id(self) -> str:
        """The relative ID (without the workflow part).

        Examples:
            >>> Tokens('~u/w//c/t/01').relative_id
            'c/t/01'
            >>> Tokens('~u/w').relative_id
            Traceback (most recent call last):
            ValueError: No tokens provided

        """
        return detokenise(self.task, relative=True)

    @property
    def relative_id_with_selectors(self) -> str:
        """The relative ID (without the workflow part), with selectors.

        Examples:
            >>> Tokens('~u/w//c/t:failed/01').relative_id
            'c/t/01'
            >>> Tokens('~u/w//c/t:failed/01').relative_id_with_selectors
            'c/t:failed/01'

        """
        return detokenise(self.task, relative=True, selectors=True)

    @property
    def workflow_id(self) -> str:
        """The workflow id (without the relative part).

        Examples:
            >>> Tokens('~u/w//c/t/01').workflow_id
            '~u/w'
            >>> Tokens('c/t/01', relative=True).workflow_id
            Traceback (most recent call last):
            ValueError: No tokens provided

        """
        return detokenise(self.workflow)

    @property
    def lowest_token(self) -> str:
        """Return the lowest token present in a tokens dictionary.

        Examples:
            >>> Tokens('~u/w//c/t/01').lowest_token
            'job'
            >>> Tokens('~u/w//c/t').lowest_token
            'task'
            >>> Tokens('~u/w//c').lowest_token
            'cycle'
            >>> Tokens('~u/w//').lowest_token
            'workflow'
            >>> Tokens('~u').lowest_token
            'user'
            >>> Tokens().lowest_token({})
            Traceback (most recent call last):
            ValueError: No tokens defined

        """
        for token in reversed(IDTokens):
            if token.value in self and self[token.value]:
                return token.value
        raise ValueError('No tokens defined')

    def pop_token(self) -> Tuple[str, str]:
        """Pop the lowest token.

        Examples:
            >>> tokens = Tokens('~u/w//c/t/01')
            >>> tokens.pop_token()
            ('job', '01')
            >>> tokens.pop_token()
            ('task', 't')
            >>> tokens.pop_token()
            ('cycle', 'c')
            >>> tokens.pop_token()
            ('workflow', 'w')
            >>> tokens.pop_token()
            ('user', 'u')
            >>> tokens
            <id: >
            >>> tokens.pop_token()
            Traceback (most recent call last):
            KeyError: No defined tokens.

        """
        for token in reversed(IDTokens):
            token_name = token.value
            value = self[token_name]
            if value:
                self.pop(token_name)
                return (token_name, value)
        raise KeyError('No defined tokens.')

    @property
    def is_task_like(self) -> bool:
        """Returns True if any task-like objects are present in the ID.

        Task like == cycles or tasks or jobs.

        Examples:
            >>> Tokens('workflow//').is_task_like
            False
            >>> Tokens('workflow//1').is_task_like
            True

        """
        return any(
            self[key] for key in self._TASK_LIKE_KEYS
        )

    @property
    def task(self) -> 'Tokens':
        """The task portion of the tokens.

        Examples:
            >>> Tokens('~user/workflow//cycle/task/01').task
            <id: //cycle/task/01>

        """
        return Tokens(
            **{
                key: value
                for key, value in self.items()
                if key in self._TASK_LIKE_KEYS
            }
        )

    @property
    def workflow(self) -> 'Tokens':
        """The workflow portion of the tokens.

        Examples:
            >>> Tokens('~user/workflow//cycle/task/01').workflow
            <id: ~user/workflow>

        """
        return Tokens(
            **{
                key: value
                for key, value in self.items()
                if key not in self._TASK_LIKE_KEYS
            }
        )

    @property
    def is_null(self) -> bool:
        """Returns True if no tokens are set.

        Examples:
            >>> tokens = Tokens()
            >>> tokens.is_null
            True
            >>> tokens['job_sel'] = 'x'
            >>> tokens.is_null
            True
            >>> tokens['job'] = '01'
            >>> tokens.is_null
            False

        """
        return not any(
            self[key] for key in self._REGULAR_KEYS
        )

    def update_tokens(
        self,
        tokens: 'Optional[Tokens]' = None,
        **kwargs
    ) -> None:
        """Update the tokens dictionary.

        Similar to dict.update but with an optional Tokens argument.

        Examples:
            >>> tokens = Tokens('x')
            >>> tokens.update_tokens(workflow='y')
            >>> tokens
            <id: y>
            >>> tokens.update_tokens(Tokens('z'))
            >>> tokens
            <id: z>
            >>> tokens.update_tokens(Tokens('a'), cycle='b')
            >>> tokens
            <id: a//b>

        """
        if tokens:
            for key, value in tokens.items():
                self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    def update(self, other):
        """dict.update.

        Example:
            >>> tokens = Tokens(workflow='w')
            >>> tokens.update({'cycle': 'c'})
            >>> tokens.id
            'w//c'

        """
        return self.update_tokens(**other)

    def duplicate(
        self,
        tokens: 'Optional[Tokens]' = None,
        **kwargs
    ) -> 'Tokens':
        """Duplicate a tokens object.

        Can be used to change the values of the new object at the same time.

        Examples:
            Duplicate tokens:
            >>> tokens1 = Tokens('~u/w')
            >>> tokens2 = tokens1.duplicate()

            The copy is equal but a different object:
            >>> tokens1 == tokens2
            True
            >>> id(tokens1) == id(tokens2)
            False

            Make a copy and modify it:
            >>> tokens1.duplicate(cycle='1').id
            '~u/w//1'

            Original not changed
            >>> tokens1.id
            '~u/w'
        """
        ret = Tokens(self)
        ret.update_tokens(tokens, **kwargs)
        return ret


# //cycle[:sel][/task[:sel][/job[:sel]]]
RELATIVE_PATTERN = rf'''
    //
    (?P<{IDTokens.Cycle.value}>[^~\/:\n]+)
    (?:
      :
      (?P<{IDTokens.Cycle.value}_sel>[^\/:\n]+)
    )?
    (?:
      /
      (?:
        (?P<{IDTokens.Task.value}>[^\/:\n]+)
        (?:
          :
          (?P<{IDTokens.Task.value}_sel>[^\/:\n]+)
        )?
        (?:
          /
          (?:
            (?P<{IDTokens.Job.value}>[^\/:\n]+)
            (?:
              :
              (?P<{IDTokens.Job.value}_sel>[^\/:\n]+)
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
            (?P<{IDTokens.User.value}>[^\/:\n~]+)
            # allow the match to end here
            (\/|$)
          )
          |^
        )
        (?:
          (?P<{IDTokens.Workflow.value}>
            # can't begin with //
            (?!//)
            # workflow ID (flat)
            [^:~\n\/]+
            # workflow ID (hierarchical)
            (?:
              (?:
                \/
                [^:~\n\/]+
              )+
            )?

          )
          (?:
            :
            (?P<{IDTokens.Workflow.value}_sel>[^\/:\n]+)
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
        (?P<{IDTokens.Task.value}>[^~\:\/\n]+)
        \.
        # NOTE: legacy cycles always start with a number
        (?P<{IDTokens.Cycle.value}>\d[^~\.\:\/\n]*)
        # NOTE: the task selector applied to the cycle in this legacy format
        # (not a mistake)
        (?:
            :
            (?P<{IDTokens.Task.value}_sel>[^\:\/\n]+)
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
        (?P<{IDTokens.Cycle.value}>\d[^~\.\:\/\n]+)
        \/
        # NOTE: task names can contain "."
        (?P<{IDTokens.Task.value}>[^~\:\/\n]+)
        (?:
            :
            (?P<{IDTokens.Task.value}_sel>[^\:\/\n]+)
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


def legacy_tokenise(identifier: str) -> Tokens:
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
) -> Tokens:
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
        ...     'cycle:cycle_sel/task:task_sel/01:job_sel'
        ... ) # doctest: +NORMALIZE_WHITESPACE
        <id: ~user/workflow//cycle/task/01>

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
            return Tokens(**_dict_strip(match.groupdict()))
    raise ValueError(f'Invalid Cylc identifier: {identifier}')


def detokenise(
    tokens: Tokens,
    selectors: bool = False,
    relative: bool = False,
) -> str:
    """Convert Cylc tokens into a string identifier.

    Args:
        tokens (dict):
            IDTokens as returned by tokenise.
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
    keys = {
        key for key in Tokens._REGULAR_KEYS
        if tokens.get(key)
    }
    is_relative = keys.isdisjoint(('user', 'workflow'))
    is_partial = keys.isdisjoint(('cycle', 'task', 'job'))
    if is_relative and is_partial:
        raise ValueError('No tokens provided')

    # determine the lowest token
    for lowest_token in reversed(IDTokens):
        if lowest_token.value in keys:
            break

    highest_token: Optional[IDTokens]
    identifier = []
    if is_relative:
        highest_token = IDTokens.Cycle
        if not relative:
            identifier = ['/']
    else:
        highest_token = IDTokens.User

    for token in IDTokens:
        if highest_token:
            if token != highest_token:
                continue
            highest_token = None
        value: Optional[str] = tokens.get(token.value)
        if not value and token == IDTokens.User:
            continue
        elif token == IDTokens.User:
            value = f'~{value}'
        elif token == IDTokens.Job and value != 'NN':
            value = f'{int(value):02}'  # type: ignore[arg-type]
        value = value or '*'
        if selectors and tokens.get(token.value + '_sel'):
            # include selectors
            value = f'{value}:{tokens[token.value + "_sel"]}'
        if token == IDTokens.Workflow and not is_partial:
            value += '/'
        identifier.append(value)

        if token == lowest_token:
            break

    return '/'.join(identifier)


def upgrade_legacy_ids(*ids: str, relative=False) -> List[str]:
    """Reformat IDs from legacy to contemporary format:

    If no upgrading is required it returns the identifiers unchanged.

    Args:
        *ids:
            Identifier list.
        relative:
            If `False` then `ids` must describe absolute ID(s) e.g:
                workflow task1.cycle1 task2.cycle2
            If `True` then `ids` should be relative e.g:
                task1.cycle1 task2.cycle2

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

        # upgrade relative IDs:
        >>> upgrade_legacy_ids('x.1', relative=True)
        ['1/x']
        >>> upgrade_legacy_ids('x.1', 'x.2', 'x.3:s', relative=True)
        ['1/x', '2/x', '3/x:s']

    """
    if not relative and len(ids) < 2:
        # only legacy relative references require upgrade => abort
        return list(ids)

    legacy_ids: List[str]
    _ids: Iterable[str]
    if relative:
        legacy_ids = []
        _ids = ids
    else:
        legacy_ids = [ids[0]]
        _ids = ids[1:]

    for id_ in _ids:
        try:
            tokens = legacy_tokenise(id_)
        except ValueError:
            # not a valid legacy token => abort
            return list(ids)
        else:
            # upgrade this token
            legacy_ids.append(
                detokenise(tokens, selectors=True, relative=relative)
            )

    LOG.warning(
        f'Cylc7 format is deprecated, using: {" ".join(legacy_ids)}'
        ' (see "cylc help id")'
    )
    return legacy_ids


def contains_multiple_workflows(tokens_list: List[Tokens]) -> bool:
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
