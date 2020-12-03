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
"""Load custom variables for template processor."""

import ast

from cylc.flow.exceptions import UserInputError
from cylc.flow.safe_eval import SafeVisitor


def load_template_vars(template_vars=None, template_vars_file=None):
    """Load template variables from key=value strings."""
    res = {}
    if template_vars_file:
        for line in open(template_vars_file):
            line = line.strip().split("#", 1)[0]
            if not line:
                continue
            key, val = line.split("=", 1)
            res[key.strip()] = templatevar_eval(val.strip())
    if template_vars:
        for pair in template_vars:
            key, val = pair.split("=", 1)
            res[key.strip()] = templatevar_eval(val.strip())
    return res


def listrange(*args):
    """A list equivalent to the Python range() function.

    Equivalent to list(range(*args))

    Examples:
        >>> listrange(3)
        [0, 1, 2]
        >>> listrange(0, 5, 2)
        [0, 2, 4]

    """
    return list(range(*args))


class SimpleVisitor(SafeVisitor):
    """Abstract syntax tree node visitor for simple safe operations."""

    whitelisted_nodes = (
        # top-level expression node
        ast.Expression,
        # constants: python3.8+
        ast.Constant,  # !!!
        # contants: python3.7
        ast.NameConstant,  # !!!
        ast.Num,
        ast.Str,
        # collections
        ast.Load,
        ast.List,
        ast.Tuple,
        ast.Set,  # !!!
        ast.Dict,
        # function calls (note only allow whitelisted calls)
        ast.Call,
        ast.Name
    )

    whitelisted_functions = (
        'range',
        'listrange'
    )


def _templatevar_eval(expr, **variables):
    """Safely evaluates template variables from strings.

    Examples:
        # constants
        >>> _templatevar_eval('"str"')
        'str'
        >>> _templatevar_eval('True')
        True
        >>> _templatevar_eval('1')
        1
        >>> _templatevar_eval('1.1')
        1.1
        >>> _templatevar_eval('None')

        # lists
        >>> _templatevar_eval('[]')
        []
        >>> _templatevar_eval('["str", True, 1, 1.1, None]')
        ['str', True, 1, 1.1, None]

        # tuples
        >>> _templatevar_eval('()')
        ()
        >>> _templatevar_eval('("str", True, 1, 1.1, None)')
        ('str', True, 1, 1.1, None)

        # sets
        >>> _templatevar_eval('{"str", True, 1, 1.1, None}') == (
        ... {'str', True, 1, 1.1, None})
        True

        # dicts
        >>> _templatevar_eval('{}')
        {}
        >>> _templatevar_eval(
        ... '{"a": "str", "b": True, "c": 1, "d": 1.1, "e": None}')
        {'a': 'str', 'b': True, 'c': 1, 'd': 1.1, 'e': None}

        # range
        >>> _templatevar_eval('range(10)')
        range(0, 10)

        # listrange
        >>> _templatevar_eval('listrange(3)')
        [0, 1, 2]

        # errors
        >>> _templatevar_eval('1 + 1')
        Traceback (most recent call last):
        ValueError: <class '_ast.BinOp'>
        >>> _templatevar_eval('[0] + [1]')
        Traceback (most recent call last):
        ValueError: <class '_ast.BinOp'>
        >>> _templatevar_eval('list()')
        Traceback (most recent call last):
        ValueError: list
        >>> _templatevar_eval('__import__("shutil")')
        Traceback (most recent call last):
        ValueError: __import__

    """
    node = ast.parse(expr.strip(), mode='eval')
    SimpleVisitor().visit(node)
    # acceptable use of eval due to restricted language features
    return eval(  # nosec
        compile(node, '<string>', 'eval'),
        {'__builtins__': __builtins__, 'listrange': listrange},
        variables
    )


def templatevar_eval(var):
    """Parse tempalate variables from strings.

    Note:
        Wraps _templatevar_eval to provide more helpful error.

    Examples:
        # valid template variables
        >>> templatevar_eval('42')
        42
        >>> templatevar_eval('"string"')
        'string'
        >>> templatevar_eval('listrange(0, 3)')
        [0, 1, 2]

        # invalid templte variables
        >>> templatevar_eval('string')
        Traceback (most recent call last):
        cylc.flow.exceptions.UserInputError: Invalid template variable: string
        (note string values must be quoted)
        >>> templatevar_eval('[')
        Traceback (most recent call last):
        cylc.flow.exceptions.UserInputError: Invalid template variable: [
        (values must be valid Python literals)
        >>> templatevar_eval('MYVAR | len')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        cylc.flow.exceptions.UserInputError: \
        Invalid template variable: MYVAR | len
        Cannot use Jinja2 expressions.
        >>> templatevar_eval('range(5) | list')  # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        cylc.flow.exceptions.UserInputError: \
        Invalid template variable: range(5) | list
        Cannot use Jinja2 expressions.
        Use listrange(...) instead of range(...) | list

    """
    try:
        return _templatevar_eval(var)
    except ValueError:
        if (
            'range' in var
            and any(
                part.strip().startswith('list')
                for part in var.split('|')
            )
        ):
            raise UserInputError(
                f'Invalid template variable: {var}'
                '\nCannot use Jinja2 expressions.'
                '\nUse listrange(...) instead of range(...) | list'
            ) from None
        elif any(
            string in var
            for string in (
                '|len',
                '| len',
                '| list',
                ']+range',
                '] + range',
                ']+[',
                '] + [',
            )
        ):
            raise UserInputError(
                f'Invalid template variable: {var}'
                '\nCannot use Jinja2 expressions.'
            ) from None
        else:
            raise UserInputError(
                f'Invalid template variable: {var}'
                '\n(note string values must be quoted)'
            ) from None
    except SyntaxError:
        raise UserInputError(
            f'Invalid template variable: {var}'
            '\n(values must be valid Python literals)'
        ) from None
