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

import re
from textwrap import dedent

from cylc.flow.exceptions import InputError
from cylc.flow.parsec.exceptions import Jinja2Error

import pytest


@pytest.fixture
def flow_cylc(tmp_path):
    """Write a flow.cylc file containing the provided text."""
    def _inner(text):
        nonlocal tmp_path
        (tmp_path / 'flow.cylc').write_text(dedent(text).strip())
        return tmp_path

    return _inner


@pytest.mark.parametrize(
    'line',
    [
        pytest.param("raise('some error message')", id='raise'),
        pytest.param("assert(False, 'some error message')", id='assert'),
    ],
)
def test_raise_helper(flow_cylc, validate, line, monkeypatch):
    """It should raise an error from within Jinja2."""
    # it should raise a minimal InputError
    # (because assert/raise are used to validate inputs)
    # - intended for users of the workflow
    src_dir = flow_cylc(f'''
        #!Jinja2
        {{{{ {line} }}}}
    ''')
    with pytest.raises(
        InputError,
        match=(
            r'^some error message'
            r'\n\(add --verbose for more context\)$'
        ),
    ):
        validate(src_dir)

    # in verbose mode, it should raise the full error
    # (this includes the Jinja2 context including file/line info)
    # - intended for developers of the workflow
    monkeypatch.setattr('cylc.flow.flags.verbosity', 1)
    with pytest.raises(
        Jinja2Error,
        match=(
            r'^some error message'
            r'\nFile /.*/pytest-.*/test_.*/flow.cylc'
            r'\n  #!Jinja2'
            r'\n  \{\{ ' + re.escape(line) + r' \}\}'
            r'\t<-- Jinja2AssertionError$'
        )
    ):
        validate(src_dir)
