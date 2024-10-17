#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Test check functions in the `cylc lint` CLI Utility."""

import doctest
import json
import pytest
import re

from cylc.flow.scripts import lint

VARS = re.compile(r'\{(.*)\}')

# Functions in Cylc Lint defined with "check_*
CHECKERS = [
    getattr(lint, i) for i in lint.__dir__() if i.startswith('check_')]
# List of checks defined as checks by Cylc Lint
ALL_CHECKS = [
    *lint.MANUAL_DEPRECATIONS.values(),
    *lint.STYLE_CHECKS.values(),
]

finder = doctest.DocTestFinder()


@pytest.mark.parametrize(
    'check',
    # Those checks that have custom checker functions
    # and a short message with variables to insert:
    [
        pytest.param(c, id=c.get('function').__name__) for c in ALL_CHECKS
        if c.get('function') in CHECKERS
    ]
)
def test_custom_checker_doctests(check):
    """All check functions have at least one failure doctest

    By forcing each check function to have valid doctests
    for the case that linting has failed we are able to
    check that the function outputs the correct information
    for formatting the short formats.
    """
    doctests = finder.find(check['function'])[0]

    msg = f'{check["function"].__name__}: No failure examples in doctest'
    assert any(i.want for i in doctests.examples if i.want), msg


@pytest.mark.parametrize(
    'ref, check',
    # Those checks that have custom checker functions
    # and a short message with variables to insert:
    [
        (c.get('function'), c) for c in ALL_CHECKS
        if c.get('function') in CHECKERS
        and VARS.findall(c['short'])
    ]
)
def test_custom_checkers_short_formatters(ref, check):
    """If a check message has a format string assert that the checker
    function will return a dict to be used in
    ``check['short'].format(**kwargs)``, based on doctest output.

    ref is useful to allow us to identify the check, even
    though not used in the test.
    """
    doctests = finder.find(check['function'])[0]

    # Filter doctest examples for cases where there is a json parsable
    # want.
    examples = [
        eg for eg in [
            json.loads(e.want.replace("'", '"'))
            for e in doctests.examples if e.want
        ]
        if eg
    ]

    # Formatting using the example output changes the check short text:
    for example in examples:
        assert check['short'].format(**example) != check['short']
