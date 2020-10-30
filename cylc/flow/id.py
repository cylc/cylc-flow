from enum import Enum
import re

from cylc.flow import LOG


class Tokens(Enum):
    """Cylc object identifier tokens."""

    User = 'user'
    Flow = 'flow'
    Cycle = 'cycle'
    Task = 'task'
    Job = 'job'


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
          (?P<{Tokens.Flow.value}>[^\/:\n~]+)
          (?:
            :
            (?P<{Tokens.Flow.value}_sel>[^\/:\n]+)
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
        The tokenise() function will parse a legacy token as a "flow".

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
        Will parse a legacy (task and or cycle) token as a "flow".

    Raises:
        ValueError:
            For invalid identifiers.

    Examples:
        # absolute identifiers
        >>> tokenise(
        ...     '~user/flow:flow_sel//'
        ...     'cycle:cycle_sel/task:task_sel/job:job_sel'
        ... ) # doctest: +NORMALIZE_WHITESPACE
        {'user': 'user',
         'flow': 'flow',
         'flow_sel': 'flow_sel',
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
        >>> _(tokenise('flow//cycle'))
        {'flow': 'flow', 'cycle': 'cycle'}

        # "partial" identifiers:
        >>> _(tokenise('~user'))
        {'user': 'user'}
        >>> _(tokenise('~user/flow'))
        {'user': 'user', 'flow': 'flow'}
        >>> _(tokenise('flow'))
        {'flow': 'flow'}

        # "relative" identifiers (new syntax):
        >>> _(tokenise('//cycle'))
        {'cycle': 'cycle'}
        >>> _(tokenise('//cycle/task/job'))
        {'cycle': 'cycle', 'task': 'task', 'job': 'job'}

        # whitespace stripping is employed on all values:
        >>> _(tokenise(' flow // cycle '))
        {'flow': 'flow', 'cycle': 'cycle'}

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


def detokenise(tokens, selectors=False):
    """Convert Cylc tokens into a string identifier.

    Args:
        tokens (dict):
            Tokens as returned by tokenise.
        selectors (bool):
            If true selectors (i.e. :sel) will be included in the output.

    Returns:
        str - Identifier i.e. ~user/flow//cycle/task/job

    Raises:
        ValueError:
            For invalid or empty tokens.

    Examples:
        # absolute references:
        >>> detokenise(tokenise('~user'))
        '~user'
        >>> detokenise(tokenise('~user/flow'))
        '~user/flow'
        >>> detokenise(tokenise('~user/flow//cycle'))
        '~user/flow//cycle'
        >>> detokenise(tokenise('~user/flow//cycle/task'))
        '~user/flow//cycle/task'
        >>> detokenise(tokenise('~user/flow//cycle/task/job'))
        '~user/flow//cycle/task/job'

        # relative references:
        >>> detokenise(tokenise('//cycle/task/job'))
        '//cycle/task/job'

        # selectors are enabled using the selectors kwarg:
        >>> detokenise(tokenise('flow:a//cycle:b/task:c/job:d'))
        'flow//cycle/task/job'
        >>> detokenise(tokenise('flow:a//cycle:b/task:c/job:d'), True)
        'flow:a//cycle:b/task:c/job:d'

        # missing tokens expand to '*' (absolute):
        >>> tokens = tokenise('~user/flow//cycle/task/job')
        >>> tokens.pop('task')
        'task'
        >>> detokenise(tokens)
        '~user/flow//cycle/*/job'

        # missing tokens expand to '*' (relative):
        >>> tokens = tokenise('//cycle/task/job')
        >>> tokens.pop('task')
        'task'
        >>> detokenise(tokens)
        '//cycle/*/job'

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
    is_relative = not toks & {'user', 'flow'}
    is_partial = not toks & {'cycle', 'task', 'job'}
    if is_relative and is_partial:
        raise ValueError('No tokens provided')

    for lowest_token in reversed(Tokens):
        if lowest_token.value in toks:
            break

    if is_relative:
        highest_token = Tokens.Cycle
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
        value = value or '*'
        if selectors and tokens.get(token.value + '_sel'):
            # include selectors
            value = f'{value}:{tokens[token.value + "_sel"]}'
        if token == Tokens.Flow and not is_partial:
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
        >>> upgrade_legacy_ids('flow')
        ('flow',)

        >>> upgrade_legacy_ids('flow', '//cycle')
        ('flow', '//cycle')

        # upgrade legacy task.cycle ids:
        >>> upgrade_legacy_ids('flow', 'task.123', 'task.234')
        ['flow', '//123/task', '//234/task']

        # upgrade legacy cycle/task ids:
        >>> upgrade_legacy_ids('flow', '123/task', '234/task')
        ['flow', '//123/task', '//234/task']

        # upgrade mixed legacy ids:
        >>> upgrade_legacy_ids('flow', 'task.123', '234/task')
        ['flow', '//123/task', '//234/task']

        # upgrade legacy task states:
        >>> upgrade_legacy_ids('flow', 'task.123:abc', '234/task:def')
        ['flow', '//123/task:abc', '//234/task:def']

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


def parse_ids(*ids):
    """
    Examples:
        # parse to tokens then detokenise back
        >>> parse_back = lambda *ids: list(map(detokenise, parse_ids(*ids)))

        # list of workflows:
        >>> parse_back('flow')
        ['flow']

        >>> parse_back('flow1', 'flow2')
        ['flow1', 'flow2']

        # relative references:
        >>> parse_back('flow', '//cycle1', '//cycle2')
        ['flow//cycle1', 'flow//cycle2']

        # multiple relative references:
        >>> parse_back('flow1', '//cycle', 'flow2', '//cycle', 'flow3')
        ['flow1//cycle', 'flow2//cycle', 'flow3']

        # legacy ids:
        >>> parse_back('flow', 'task.123', 'a.b.c.234', '345/task')
        ['flow//123/task', 'flow//234/a.b.c', 'flow//345/task']

        # errors:
        >>> parse_back('//cycle')
        Traceback (most recent call last):
        ValueError: Relative reference must follow an incomplete one.
        E.G: flow //cycle/task

        >>> parse_back('flow//cycle', '//cycle')
        Traceback (most recent call last):
        ValueError: Relative reference must follow an incomplete one.
        E.G: flow //cycle/task

    """
    # upgrade legacy ids if required
    ids = upgrade_legacy_ids(*ids)

    partials = None
    partials_expended = False
    tokens_list = []
    for id_ in ids:
        tokens = tokenise(id_)
        is_partial = tokens.get('flow') and not tokens.get('cycle')
        is_relative = not tokens.get('flow')

        if partials:
            # we previously encountered a flow ID which did not specify a
            # cycle
            if is_partial:
                # this is an absolute ID
                if not partials_expended:
                    # no relative references were made to the previous ID
                    # so add the whole flow to the tokens list
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
                    '\nE.G: flow //cycle/task'
                )
            else:
                tokens_list.append(tokens)

    if partials and not partials_expended:
        # if the last ID was a "partial" but not expanded add it to the list
        tokens_list.append(tokens)

    return tokens_list


import pytest


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        '~user//cycle'
        '~flow:state',
        'flow:flow_sel:flow_sel',
    ]
)
def test_univseral_id_illegal(identifier):
    """Test illegal formats of the universal identifier."""
    assert UNIVERSAL_ID.match(identifier) is None


@pytest.mark.parametrize(
    'identifier',
    [
        '~user',
        '~user/',
        '~user/flow',
        '~user/flow//',
        '~user/flow:flow_sel',
        '~user/flow:flow_sel//',
        '~user/flow:flow_sel//cycle',
        '~user/flow:flow_sel//cycle/',
        '~user/flow:flow_sel//cycle:cycle_sel',
        '~user/flow:flow_sel//cycle:cycle_sel/',
        '~user/flow:flow_sel//cycle:cycle_sel/task',
        '~user/flow:flow_sel//cycle:cycle_sel/task/',
        '~user/flow:flow_sel//cycle:cycle_sel/task:task_sel',
        '~user/flow:flow_sel//cycle:cycle_sel/task:task_sel/',
        '~user/flow:flow_sel//cycle:cycle_sel/task:task_sel/job',
        '~user/flow:flow_sel//cycle:cycle_sel/task:task_sel/job:job_sel',
        'flow',
        'flow//',
        'flow:flow_sel',
        'flow:flow_sel//',
        'flow:flow_sel//cycle',
        'flow:flow_sel//cycle/',
        'flow:flow_sel//cycle:cycle_sel',
        'flow:flow_sel//cycle:cycle_sel/',
        'flow:flow_sel//cycle:cycle_sel/task',
        'flow:flow_sel//cycle:cycle_sel/task/',
        'flow:flow_sel//cycle:cycle_sel/task:task_sel',
        'flow:flow_sel//cycle:cycle_sel/task:task_sel/',
        'flow:flow_sel//cycle:cycle_sel/task:task_sel/job',
        'flow:flow_sel//cycle:cycle_sel/task:task_sel/job:job_sel'
    ]
)
def test_universal_id_matches(identifier):
    """test every legal format of the universal identifier."""
    expected_tokens = {
        'user': 'user' if 'user' in identifier else None,
        'flow': 'flow' if 'flow' in identifier else None,
        'flow_sel': 'flow_sel' if 'flow_sel' in identifier else None,
        'cycle': 'cycle' if 'cycle' in identifier else None,
        'cycle_sel': 'cycle_sel' if 'cycle_sel' in identifier else None,
        'task': 'task' if 'task' in identifier else None,
        'task_sel': 'task_sel' if 'task_sel' in identifier else None,
        'job': 'job' if 'job' in identifier else None,
        'job_sel': 'job_sel' if 'job_sel' in identifier else None
    }
    match = UNIVERSAL_ID.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        ':',
        'flow//cycle',
        'task:task_sel:task_sel',
        'cycle/task'
        '//',
        '//~',
        '//:',
        '//flow//cycle',
        '//task:task_sel:task_sel'
    ]
)
def test_relative_id_illegal(identifier):
    """Test illegal formats of the universal identifier."""
    assert RELATIVE_ID.match(identifier) is None


@pytest.mark.parametrize(
    'identifier',
    [
        '//cycle',
        '//cycle/',
        '//cycle:cycle_sel',
        '//cycle:cycle_sel/',
        '//cycle:cycle_sel/task',
        '//cycle:cycle_sel/task/',
        '//cycle:cycle_sel/task:task_sel',
        '//cycle:cycle_sel/task:task_sel/',
        '//cycle:cycle_sel/task:task_sel/job',
        '//cycle:cycle_sel/task:task_sel/job:job_sel',
    ]
)
def test_relative_id_matches(identifier):
    """test every legal format of the relative identifier."""
    expected_tokens = {
        'cycle': 'cycle' if 'cycle' in identifier else None,
        'cycle_sel': 'cycle_sel' if 'cycle_sel' in identifier else None,
        'task': 'task' if 'task' in identifier else None,
        'task_sel': 'task_sel' if 'task_sel' in identifier else None,
        'job': 'job' if 'job' in identifier else None,
        'job_sel': 'job_sel' if 'job_sel' in identifier else None
    }
    match = RELATIVE_ID.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        '/',
        ':',
        'task.cycle',  # the first digit of the cycle should be a number
        '//task.123',  # don't match the new format
        'task.cycle/job',
        'task:task_sel.123'  # selector should suffix the cycle
    ]
)
def test_legacy_task_dot_cycle_illegal(identifier):
    """Test illegal formats of the legacy task.cycle identifier."""
    assert LEGACY_TASK_DOT_CYCLE.match(identifier) is None


@pytest.mark.parametrize(
    'identifier,expected_tokens',
    [
        (
            'task.123',
            {'task': 'task', 'cycle': '123', 'task_sel': None}
        ),
        (
            't.a.s.k.123',
            {'task': 't.a.s.k', 'cycle': '123', 'task_sel': None}
        ),
        (
            'task.123:task_sel',
            {'task': 'task', 'cycle': '123', 'task_sel': 'task_sel'}
        )
    ]
)
def test_legacy_task_dot_cycle_matches(identifier, expected_tokens):
    match = LEGACY_TASK_DOT_CYCLE.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens


@pytest.mark.parametrize(
    'identifier',
    [
        '',
        '~',
        '/',
        ':',
        'cycle/task',  # the first digit of the cycle should be a number
        '//123/task',  # don't match the new format
        'cycle/task/job'
    ]
)
def test_legacy_cycle_slash_task_illegal(identifier):
    """Test illegal formats of the legacy cycle/task identifier."""
    assert LEGACY_CYCLE_SLASH_TASK.match(identifier) is None


@pytest.mark.parametrize(
    'identifier,expected_tokens',
    [
        (
            '123/task',
            {'task': 'task', 'cycle': '123', 'task_sel': None}
        ),
        (
            '123/t.a.s.k',
            {'task': 't.a.s.k', 'cycle': '123', 'task_sel': None}
        ),
        (
            '123/task:task_sel',
            {'task': 'task', 'cycle': '123', 'task_sel': 'task_sel'}
        )
    ]
)
def test_legacy_cycle_slash_task_matches(identifier, expected_tokens):
    match = LEGACY_CYCLE_SLASH_TASK.match(identifier)
    assert match
    assert match.groupdict() == expected_tokens
