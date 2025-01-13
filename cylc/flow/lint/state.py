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
"""Cylc Linter state store object.
"""

from dataclasses import dataclass
import re


@dataclass
class LinterState:
    """A place to keep linter state"""
    TRIPLE_QUOTES = re.compile(r'\'{3}|\"{3}')
    JINJA2_START = re.compile(r'{%')
    JINJA2_END = re.compile(r'%}')
    NEW_SECTION_START = re.compile(r'^[^\[]*\[[^\[]')
    is_metadata_section: bool = False
    is_multiline_chunk: bool = False
    is_jinja2_block: bool = False
    jinja2_shebang: bool = False
    line_no: int = 1

    def skip_line(self, line):
        """Is this a line we should skip, according to state we are holding
        and the line content?

        TODO: Testme
        """
        return any((
            self.skip_metatadata_desc(line),
            self.skip_jinja2_block(line)
        ))

    def skip_metatadata_desc(self, line):
        """Should we skip this line because it's part of a metadata multiline
        description section.

        TODO: Testme
        """
        if '[meta]' in line:
            self.is_metadata_section = True
        elif self.is_metadata_section and self.is_end_of_meta_section(line):
            self.is_metadata_section = False

        if self.is_metadata_section:
            if self.TRIPLE_QUOTES.findall(line):
                self.is_multiline_chunk = not self.is_multiline_chunk
            if self.is_multiline_chunk:
                return True

        return False

    def skip_jinja2_block(self, line):
        """Is this line part of a jinja2 block?

        TODO: Testme
        """
        if self.jinja2_shebang:
            if (
                self.JINJA2_START.findall(line)
                and not self.JINJA2_END.findall(line)
            ):
                self.is_jinja2_block = True
            elif self.is_jinja2_block and self.JINJA2_END.findall(line):
                self.is_jinja2_block = False
                return True

        return self.is_jinja2_block

    @staticmethod
    def is_end_of_meta_section(line):
        """Best tests I can think of for end of metadata section.

        Exists as separate function to improve documentation of what we
        look for as the end of the meta section.

        Examples:
            >>> this = LinterState.is_end_of_meta_section
            >>> this('[scheduler]')   # Likely right answer
            True
            >>> this('[garbage]')   # Unreasonable, not worth guarding against
            True
            >>> this('')
            False
            >>> this('    ')
            False
            >>> this('{{NAME}}')
            False
            >>> this('    [[custom metadata subsection]]')
            False
            >>> this('[[custom metadata subsection]]')
            False
            >>> this('arbitrary crud')
            False
        """
        return bool(line and LinterState.NEW_SECTION_START.findall(line))
