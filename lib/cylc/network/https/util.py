#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Utility classes for HTTPS servers and clients."""

import HTMLParser


class ExceptionPreReader(HTMLParser.HTMLParser):

    def __init__(self):
        self.is_in_traceback_pre = False
        self.exception_text = None
        # Can't use super because this is an old-style class... :(
        HTMLParser.HTMLParser.__init__(self)

    def handle_starttag(self, tag, attributes):
        if tag != "pre":
            return
        for name, value in attributes:
            if name == "id" and value == "traceback":
                self.is_in_traceback_pre = True

    def handle_endtag(self, tag):
        self.is_in_traceback_pre = False

    def handle_data(self, data):
        if hasattr(self, "is_in_traceback_pre") and self.is_in_traceback_pre:
            if self.exception_text is None:
                self.exception_text = ""
            self.exception_text += data


def get_exception_from_html(html_text):
    """Return any content inside a <pre> block with id 'traceback', or None.

    Return e.g. 'abcdef' for text like '<body><pre id="traceback">
    abcdef
    </pre></body>'.

    """
    parser = ExceptionPreReader()
    try:
        parser.feed(parser.unescape(html_text))
        parser.close()
    except HTMLParser.HTMLParseError:
        return None
    return parser.exception_text


def unicode_encode(data):
    if isinstance(data, unicode):
        return data.encode('utf-8')
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            new_dict.update(
                {unicode_encode(key): unicode_encode(value)}
            )
        return new_dict
    if isinstance(data, list):
        return [unicode_encode(item) for item in data]
    return data
