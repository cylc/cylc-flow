#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import re
import copy


class ConditionalSimplifier(object):
    """A class to simplify logical expressions"""
    REC_CONDITIONALS = re.compile("([&|()])")

    def __init__(self, expr, clean):
        self.raw_expression = expr
        self.clean_list = clean
        self.nested_expr = self.format_expr(self.raw_expression)

    def get_cleaned(self):
        """Return the simplified logical expression"""
        cleaned = self.nested_expr
        for item in self.clean_list:
            cleaned = self.clean_expr(cleaned, item)
        cleaned = self.flatten_nested_expr(cleaned)
        return cleaned

    @classmethod
    def listify(cls, message):
        """Convert a string containing a logical expression to a list

        Examples:
            >>> ConditionalSimplifier.listify('(foo)')
            ['foo']

            >>> ConditionalSimplifier.listify('foo & (bar | baz)')
            ['foo', '&', ['bar', '|', 'baz']]

            >>> ConditionalSimplifier.listify('(a&b)|(c|d)&(e|f)')
            [['a', '&', 'b'], '|', ['c', '|', 'd'], '&', ['e', '|', 'f']]

            >>> ConditionalSimplifier.listify('a & (b & c)')
            ['a', '&', ['b', '&', 'c']]

            >>> ConditionalSimplifier.listify('a & b')
            ['a', '&', 'b']

            >>> ConditionalSimplifier.listify('a & (b)')
            ['a', '&', 'b']

            >>> ConditionalSimplifier.listify('((foo)')
            Traceback (most recent call last):
            ValueError: ((foo)

            >>> ConditionalSimplifier.listify('(foo))')
            Traceback (most recent call last):
            ValueError: (foo))

        """
        message = message.replace("'", "\"")

        ret_list = []
        stack = [ret_list]
        for item in cls.REC_CONDITIONALS.split(message):
            item = item.strip()
            if item and item not in ["(", ")"]:
                stack[-1].append(item)
            elif item == "(":
                stack[-1].append([])
                stack.append(stack[-1][-1])
            elif item == ")":
                stack.pop()
                if not stack:
                    raise ValueError(message)
                if isinstance(stack[-1][-1], list) and len(stack[-1][-1]) == 1:
                    stack[-1][-1] = stack[-1][-1][0]
        if len(stack) > 1:
            raise ValueError(message)
        return ret_list

    @classmethod
    def get_bracketed(cls, nest_me):
        """Nest a list according to any brackets in it"""
        start = 0
        finish = len(nest_me)
        indices = list(range(0, len(nest_me)))
        for i in indices:
            if nest_me[i] == "(":
                start = i
                break
        else:
            return nest_me
        indices.reverse()
        for i in indices:
            if nest_me[i] == ")":
                finish = i
                break
        bracket_nested = nest_me[0:start + 1]
        bracket_nested.append(cls.get_bracketed(nest_me[start + 1:finish]))
        bracket_nested.extend(nest_me[finish:len(nest_me)])
        return bracket_nested

    @classmethod
    def nest_by_oper(cls, nest_me, oper):
        """Nest a list based on a specified logical operation"""
        found = False
        for i, _ in enumerate(nest_me):
            if isinstance(nest_me[i], list):
                nest_me[i] = cls.nest_by_oper(nest_me[i], oper)
            if nest_me[i] == oper:
                found = i
                break
        if len(nest_me) <= 3:
            return nest_me
        if found:
            nested = nest_me[0:found - 1]
            nested += [nest_me[found - 1:found + 2]]
            if (found + 2) < len(nest_me):
                nested += nest_me[found + 2:]
            return cls.nest_by_oper(nested, oper)
        else:
            return nest_me

    @classmethod
    def clean_expr(cls, nested_list, criterion):
        """Return a list with entries specified by 'criterion' removed"""
        cleaned = copy.deepcopy(nested_list)

        # Make sure that we don't have extraneous nesting.
        while (isinstance(cleaned, list) and len(cleaned) == 1 and
               isinstance(cleaned[0], list)):
            cleaned = cleaned[0]

        if len(cleaned) == 1:
            cleaned = cleaned[0]

        if isinstance(cleaned, str):
            if cleaned == criterion:
                return ""
            else:
                return cleaned

        # Recurse through the nested list and remove criterion.
        found = None
        for i, _ in enumerate(cleaned):
            if isinstance(cleaned[i], list):
                cleaned[i] = cls.clean_expr(cleaned[i], criterion)
            if cleaned[i] in [criterion, '']:
                found = i
                break

        if found is not None:
            # e.g. [ 'foo', '|', 'bar', '|']
            if found == 0:
                cleaned = cleaned[2:]
            else:
                del cleaned[found - 1:found + 1]
            return cls.clean_expr(cleaned, criterion)
        else:
            return cleaned

    @classmethod
    def format_expr(cls, expr):
        """Carry out list conversion and nesting of a logical expression in
        the correct order."""
        return cls.nest_by_oper(
            cls.nest_by_oper(cls.get_bracketed(cls.listify(expr)), "&"),
            "|")

    @classmethod
    def flatten_nested_expr(cls, expr):
        """Convert a logical expression in a nested list back to a string"""
        flattened = copy.deepcopy(expr)
        for i, _ in enumerate(flattened):
            if isinstance(flattened[i], list):
                flattened[i] = cls.flatten_nested_expr(flattened[i])
        if isinstance(flattened, list):
            flattened = " ".join(flattened)
        return "({0})".format(flattened)
