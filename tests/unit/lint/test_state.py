#!/usr/bin/env python3
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
"""Test Cylc Linter state store object.
"""

import pytest

from cylc.flow.lint.state import LinterState


param = pytest.param


@pytest.mark.parametrize(
    'is_metadata_section, is_multiline_chunk, line,'
    'after_is_metadata_section, after_is_multiline_chunk, returns',
    (
        param(
            False, False, '[meta]', True, False, False,
            id='start-meta-section'
        ),
        param(
            True, False, '[garbage]', False, False, False,
            id='end-meta-section'
        ),
        param(
            True, False, '"""', True, True, True,
            id='start-quoted-section'
        ),
        param(
            True, True, '"""', True, False, False,
            id='stop-quoted-section'
        ),
        param(
            True, False, '"""Some Stuff"""', True, False, False,
            id='dont-start-quoted-section'
        ),
        param(
            True, True, 'defintly rubish', True, True, True,
            id='should-be-ignored'
        ),
    )
)
def test_skip_metadata_desc(
    is_metadata_section,
    is_multiline_chunk,
    line,
    after_is_metadata_section,
    after_is_multiline_chunk,
    returns
):
    state = LinterState()
    state.is_metadata_section = is_metadata_section
    state.is_multiline_chunk = is_multiline_chunk

    assert state.skip_metatadata_desc(line) == returns
    assert state.is_metadata_section == after_is_metadata_section
    assert state.is_multiline_chunk == after_is_multiline_chunk


@pytest.mark.parametrize(
    'is_j2_block_before, line, is_j2_block_after, returns',
    (
        param(
            False, '{%', True, True,
            id='block-starts'
        ),
        param(
            False, '{% if something %}', False, False,
            id='no-block-starts'
        ),
        param(
            True, 'Anything Goes', True, True,
            id='block-content'
        ),
        param(
            True, '%}', False, True,
            id='block-end'
        ),
    )
)
def test_skip_jinja2_block(
    is_j2_block_before,
    line,
    is_j2_block_after,
    returns
):
    state = LinterState()
    state.jinja2_shebang = True
    state.is_jinja2_block = is_j2_block_before

    assert state.skip_jinja2_block(line) == returns
    assert state.is_jinja2_block == is_j2_block_after


@pytest.mark.parametrize(
    'line, expect',
    (
        ('', False),
        ('key=value', False),
        ('# Comment', False),
        ('Garbage', False),
        ('   indented', False),
        ('[section]', True),
        ('    [section]', True),
        ('[[subsection]]', False),
        ('    [[subsection]]', False),
    )
)
def test_NEW_SECTION_START(line, expect):
    """It correctly identifies a new section, and doesn't
    identify subsections."""
    exp = LinterState.NEW_SECTION_START
    assert bool(exp.findall(line)) == expect
