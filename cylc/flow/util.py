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
"""Misc functionality."""

import ast
from contextlib import suppress
from functools import (
    lru_cache,
    partial,
)
import json
import re
from textwrap import dedent
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
)


BOOL_SYMBOLS: Dict[bool, str] = {
    # U+2A2F (vector cross product)
    False: '⨯',
    # U+2713 (check)
    True: '✓'
}

_NAT_SORT_SPLIT = re.compile(r'([\d\.]+)')


def uniq(iterable):
    """Return a unique collection of the provided items preserving item order.

    Useful for unhashable things like dicts, relies on __eq__ for testing
    equality.

    Examples:
        >>> uniq([1, 1, 2, 3, 5, 8, 1])
        [1, 2, 3, 5, 8]

    """
    ret = []
    for item in iterable:
        if item not in ret:
            ret.append(item)
    return ret


def iter_uniq(iterable):
    """Iterate over an iterable omitting any duplicate entries.

    Useful for unhashable things like dicts, relies on __eq__ for testing
    equality.

    Note:
        More efficient than "uniq" for iteration use cases.

    Examples:
        >>> list(iter_uniq([1, 1, 2, 3, 5, 8, 1]))
        [1, 2, 3, 5, 8]

    """
    cache = set()
    for item in iterable:
        if item not in cache:
            cache.add(item)
            yield item


def sstrip(text):
    """Simple function to dedent and strip text.

    Examples:
        >>> print(sstrip('''
        ...     foo
        ...       bar
        ...     baz
        ... '''))
        foo
          bar
        baz

    """
    return dedent(text).strip()


def natural_sort_key(key: str, fcns=(int, str)) -> List[Any]:
    """Returns a key suitable for sorting.

    Splits the key into sortable chunks to preserve numerical order.

    Examples:
        >>> natural_sort_key('a1b2c3')
        ['a', 1, 'b', 2, 'c', 3]
        >>> natural_sort_key('a123b')
        ['a', 123, 'b']
        >>> natural_sort_key('a1.23b', fcns=(float, str))
        ['a', 1.23, 'b']
        >>> natural_sort_key('a.b')
        ['a', '.', 'b']

    """
    ret = []
    for item in _NAT_SORT_SPLIT.split(key):
        for fcn in fcns:
            with suppress(TypeError, ValueError):
                ret.append(fcn(item))
                break
    if ret[-1] == '':
        ret.pop(-1)
    return ret


def natural_sort(items: List[str], fcns=(int, str)) -> None:
    """Sorts a list preserving numerical order.

    Note this is an in-place sort.

    Examples:
        >>> lst = ['a10', 'a1', 'a2']
        >>> natural_sort(lst)
        >>> lst
        ['a1', 'a2', 'a10']

        >>> lst = ['a1', '1a']
        >>> natural_sort(lst)
        >>> lst
        ['1a', 'a1']

    """
    items.sort(key=partial(natural_sort_key, fcns=fcns))


def format_cmd(cmd: Sequence[str], maxlen: int = 60) -> str:
    r"""Convert a shell command list to a user-friendly representation.

    Examples:
        >>> format_cmd(['echo', 'hello', 'world'])
        'echo hello world'
        >>> format_cmd(['echo', 'hello', 'world'], 5)
        'echo \\ \n    hello \\ \n    world'

    """
    ret = []
    line = cmd[0]
    for part in cmd[1:]:
        if line and (len(line) + len(part) + 3) > maxlen:
            ret.append(line)
            line = part
        else:
            line += f' {part}'
    if line:
        ret.append(line)
    return ' \\ \n    '.join(ret)


def cli_format(cmd: List[str]):
    """Format a command list as it would appear on the command line.

    I.E. put spaces between the items in the list.

    BACK_COMPAT: cli_format
        From:
            Python 3.7
        To:
            Python 3.8
        Remedy:
            Can replace with shlex.join

    Examples:
        >>> cli_format(['sleep', '10'])
        'sleep 10'

    """
    return ' '.join(cmd)


def serialise_set(flow_nums: Optional[set] = None) -> str:
    """Convert set to json, sorted.

    For use when a sorted result is needed for consistency.

    Examples:
        >>> serialise_set({'b', 'a'})
        '["a", "b"]'
        >>> serialise_set({3, 2})
        '[2, 3]'
        >>> serialise_set()
        '[]'

    """
    return _serialise_set(tuple(sorted(flow_nums or ())))


@lru_cache(maxsize=100)
def _serialise_set(flow_nums: tuple) -> str:
    return json.dumps(flow_nums)


@lru_cache(maxsize=100)
def deserialise_set(flow_num_str: str) -> set:
    """Convert json string to set.

    Example:
    >>> deserialise_set('[2, 3]') == {2, 3}
    True
    >>> deserialise_set('[]')
    set()

    """
    return set(json.loads(flow_num_str))


def restricted_evaluator(
    *whitelist: type,
    error_class: Callable = ValueError,
) -> Callable:
    """Returns a Python eval statement restricted to whitelisted operations.

    The "eval" function can be used to run arbitrary code. This is useful
    but presents security issues. This returns an "eval" method which will
    only allow whitelisted operations to be performed allowing it to be used
    safely with user-provided input.

    The code passed into the evaluator will be parsed into an abstract syntax
    tree (AST), then that tree will be executed using Python's internal logic.
    The evaluator will check the type of each node before it is executed and
    fail with a ValueError if it is not permitted.

    The node types are documented in the ast module:
        https://docs.python.org/3/library/ast.html

    The evaluator returned is only as safe as the nodes you whitelist, read the
    docs carefully.

    Note:
        If you don't need to parse expressions, use ast.literal_eval instead.

    Args:
        whitelist:
            Types to permit e.g. `ast.Expression`, see the ast docs for
            details.
        error_class:
            An Exception class or callable which returns an Exception instance.
            This is called and its result raised in the event that an
            expression contains non-whitelisted operations. It will be provided
            with the error message as an argument, additionally the following
            keyword arguments will be provided if defined:
                expr:
                    The expression the evaluator was called with.
                expr_node:
                    The AST node containing the parsed expression.
                error_node:
                    The first non-whitelisted AST node in the expression.
                    E.G. `<AST.Sub>` for a `-` operator.
                error_type:
                    error_node.__class__.__name__.
                    E.G. `Sub` for a `-` operator.

    Returns:
        An "eval" function restricted to the whitelisted nodes.

    Examples:
        Optionally, provide an error class to be raised in the event of
        non-whitelisted syntax (or you'll get ValueError):
        >>> class RestrictedSyntaxError(Exception):
        ...     def __init__(self, message, error_node):
        ...         self.args = (str(error_node.__class__),)

        Create an evaluator, whitelisting allowed node types:
        >>> evaluator = restricted_evaluator(
        ...     ast.Expression,  # required for all uses
        ...     ast.BinOp,       # an operation (e.g. addition or division)
        ...     ast.Add,         # the "+" operator
        ...     ast.Constant,    # required for literals e.g. "1"
        ...     ast.Name,        # required for using variables in expressions
        ...     ast.Load,        # required for accessing variable values
        ...     ast.Num,         # for Python 3.7 compatibility
        ...     error_class=RestrictedSyntaxError,  # error to raise
        ... )

        This will correctly evaluate intended expressions:
        >>> evaluator('1 + 1')
        2

        But will fail if a non-whitelisted node type is present:
        >>> evaluator('1 - 1')
        Traceback (most recent call last):
        flow.util.RestrictedSyntaxError: <class ...Sub'>
        >>> evaluator('my_function()')
        Traceback (most recent call last):
        flow.util.RestrictedSyntaxError: <class ...Call'>
        >>> evaluator('__import__("os")')
        Traceback (most recent call last):
        flow.util.RestrictedSyntaxError: <class ...Call'>

        The evaluator cannot see the containing scope:
        >>> a = b = 1
        >>> evaluator('a + b')
        Traceback (most recent call last):
        NameError: name 'a' is not defined

        To use variables you must explicitly pass them in:
        >>> evaluator('a + b', a=1, b=2)
        3

    """
    # the node visitor is called for each node in the AST,
    # this is the bit which rejects types which are not whitelisted
    visitor = RestrictedNodeVisitor(whitelist)

    def _eval(expr, **variables):
        # parse the expression
        try:
            expr_node = ast.parse(expr.strip(), mode='eval')
        except SyntaxError as exc:
            raise _get_exception(
                error_class,
                f'{exc.msg}: {exc.text}',
                {'expr': expr}
            ) from None

        # check against whitelisted types
        try:
            visitor.visit(expr_node)
        except _RestrictedEvalError as exc:
            # non-whitelisted node detected in expression
            # => raise exception
            error_node = exc.args[0]
            raise _get_exception(
                error_class,
                (
                    f'Invalid expression: {expr}'
                    f'\n"{error_node.__class__.__name__}" not permitted'
                ),
                {
                    'expr': expr,
                    'expr_node': expr_node,
                    'error_node': error_node,
                    'error_type': error_node.__class__.__name__,
                },
            ) from None

        # run the expresion
        # Note: this may raise runtime errors
        return eval(  # nosec
            # acceptable use of eval as only whitelisted operations are
            # permitted
            compile(expr_node, '<string>', 'eval'),
            # deny access to builtins
            {'__builtins__': {}},
            # provide access to explicitly provided variables
            variables,
        )

    return _eval


class RestrictedNodeVisitor(ast.NodeVisitor):
    """AST node visitor which errors on non-whitelisted syntax.

    Raises _RestrictedEvalError if a non-whitelisted node is visited.
    """

    def __init__(self, whitelist):
        super().__init__()
        self._whitelist: Tuple[type] = whitelist

    def visit(self, node):
        if not isinstance(node, self._whitelist):
            # only permit whitelisted operations
            raise _RestrictedEvalError(node)
        return super().visit(node)


class _RestrictedEvalError(Exception):
    """For internal use.

    Raised in the event non-whitelisted syntax is detected in an expression.
    """

    def __init__(self, node):
        self.node = node


def _get_exception(
    error_class: Callable,
    message: str,
    context: dict
) -> Exception:
    """Helper which returns exception instances.

    Filters the arguments in context by the parameters of the error_class.

    This allows the error_class to decide what fields it wants, and for us
    to add/change these params in the future.
    """
    import inspect  # no need to import unless errors occur
    try:
        params = dict(inspect.signature(error_class).parameters)
    except ValueError:
        params = {}

    context = {
        key: value
        for key, value in context.items()
        if key in params
    }

    return error_class(message, **context)


class NameWalker(ast.NodeVisitor):
    """AST node visitor which records all variable names in an expression.

    Examples:
        >>> tree = ast.parse('(foo and bar) or baz or qux')
        >>> walker = NameWalker()
        >>> walker.visit(tree)
        >>> sorted(walker.names)
        ['bar', 'baz', 'foo', 'qux']

    """

    def __init__(self):
        super().__init__()
        self._names = set()

    def visit(self, node):
        if isinstance(node, ast.Name):
            self._names.add(node.id)
        return super().visit(node)

    @property
    def names(self):
        return self._names


def get_variable_names(expression):
    walker = NameWalker()
    walker.visit(ast.parse(expression))
    return walker.names
