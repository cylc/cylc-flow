#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

"""An extension providing pygments lexers for suite.rc files and Cylc graph
strings."""

from pygments.lexer import RegexLexer, bygroups, include
from pygments.token import (Name, Comment, Text, Operator, String,
                            Punctuation, Error, Keyword)


class CylcLexer(RegexLexer):
    """Pygments lexer for the Cylc suite.rc language."""

    # Pygments tokens for Cylc suite.rc elements which have no direct
    # translation.
    HEADING_TOKEN = Name.Tag
    SETTING_TOKEN = Name.Variable
    GRAPH_TASK_TOKEN = Keyword.Declaration
    PARAMETERISED_TASK_TOKEN = Name.Builtin
    INTERCYCLE_OFFSET_TOKEN = Name.Builtin

    # Pygments values.
    name = 'Cylc'
    aliases = ['cylc', 'suiterc']
    filenames = ['suite.rc']
    # mimetypes = ['text/x-ini', 'text/inf']

    # Patterns, rules and tokens.
    tokens = {
        'root': [
            # Jinja2 opening braces:  {{  {%  {#
            include('jinja2-openers'),

            # Jinja2 shebang:  #!Jinja2
            (r'#![Jj]inja2', Comment.Hashbang),

            # Cylc comments:  # ...
            include('comment'),

            # Leading whitespace.
            (r'^[\s\t]+', Text),

            # Cylc headings:  [<heading>]
            (r'([\[]+)', HEADING_TOKEN, 'heading'),

            # Multi-line graph sections:  graph = """ ...
            (r'(graph)(\s+)?(=)([\s+])?(\"\"\")',
                bygroups(SETTING_TOKEN,
                         Text,
                         Operator,
                         Text,
                         String.Double), 'multiline-graph'),

            # Inline graph sections:  graph = ...
            (r'(graph)(\s+)?(=)',
                bygroups(SETTING_TOKEN,
                         String,
                         Operator), 'inline-graph'),

            # Multi-line settings:  key = """ ...
            (r'(.*)(\s+)?(=)([\s+])?(\"\"\")',
                bygroups(SETTING_TOKEN,
                         Text,
                         Operator,
                         Text,
                         String.Double), 'multiline-setting'),

            # Inline settings:  key = ...
            (r'(.*)(\s+)?(=)',
                bygroups(SETTING_TOKEN,
                         Text,
                         Operator), 'setting')
        ],

        'heading': [
            (r'[\]]+', HEADING_TOKEN, '#pop'),
            include('jinja2-openers'),
            include('parameterisation'),
            (r'.', HEADING_TOKEN),
        ],

        # Cylc comments.
        'comment': [
            # Allow whitespace so this will work for comments following
            # headings.
            # NOTE: Does not highlight `${#`.
            (r'(\s+)?(?<!\$\{)(#.*)', bygroups(Text, Comment.Single))
        ],

        # The value in a key = value pair.
        'setting': [

            include('comment'),
            include('jinja2-openers'),
            (r'\\\n', String),
            (r'.', String),

        ],

        # The value in a key = """value""" pair.
        'multiline-setting': [
            (r'\"\"\"', String.Double, '#pop'),
            include('comment'),
            include('jinja2-openers'),
            (r'(\n|.)', String.Double)
        ],

        # Graph strings:  foo => bar & baz
        'graph': [
            include('jinja2-openers'),
            include('comment'),
            include('parameterisation'),
            (r'\w+', GRAPH_TASK_TOKEN),
            (r'\s', Text),
            (r'=>', Operator),
            (r'[\&\|\!]', Operator),
            (r'[\(\)]', Punctuation),
            (r'\[', Text, 'intercycle-offset'),
            (r'.', Comment)
        ],

        # Parameterised syntax:  <foo=1>
        'parameterisation': [
            (r'(\<)'  # Opening greater-than bracket.
             r'(\s?\w+\s?'  # Parameter name (permit whitespace).
             r'(?:[+-=]\s?\w+)?'  # [+-=] for selecting parameters.
             r'\s?'  # Permit whitespace.
             r'(?:'  # BEGIN optional extra parameter groups...
             r'(?:\s?,\s?\w+\s?'  # Comma seperated parameters.
             r'(?:[+-=]\s?\w+)?'  # [+-=] for selecting parameters.
             r'\s?)'  # Permit whitespace.
             r'+)?'  # ...END optional extra parameter groups.
             r')(\>)',  # Closing lesser-than bracket.
             bygroups(Text, PARAMETERISED_TASK_TOKEN, Text)),
            (r'(\<)(.*)(\>)', bygroups(Text, Error, Text))
        ],

        # Task inter-cycle offset for graphing:  foo[-P1DT1M]
        'intercycle-offset': [
            include('integer-duration'),
            include('iso8601-duration'),
            (r'[\^\$]', INTERCYCLE_OFFSET_TOKEN),
            (r'\]', Text, '#pop')
        ],

        # An integer duration:  +P1
        'integer-duration': [
            (r'[+-]P\d+(?![\w-])', INTERCYCLE_OFFSET_TOKEN)
        ],

        # An ISO8601 duration:  +P1DT1H
        'iso8601-duration': [
            # Basic format.
            (r'([+-])?P'
             r'(?![\]\s])'  # Require something to follow.
             r'('

             # Weekly format (ISO8601-1:4.4.4.5):
             r'\d{1,2}W'

             r'|'  # OR

             # Extended Format (ISO8601-1:4.4.4.4):
             r'('
             r'\d{8}T\d{6}'
             r'|'
             r'\d{4}\-\d{2}\-\d{2}T\d{2}\:\d{2}\:\d{2}'
             r')'

             r'|'  # OR

             # Basic format (ISO8601-1:4.4.4.4):
             # ..Year
             r'(\d{1,4}Y)?'
             # ..Month
             r'(\d{1,2}M)?'
             # ..Day
             r'(\d{1,2}D)?'
             r'(T'
             # ..Hours.
             r'(\d{1,2}H)?'
             # ..Minutes.
             r'(\d{1,2}M)?'
             # ..Secconds.
             r'(\d{1,2}S)?'
             r')?'

             r')',
             INTERCYCLE_OFFSET_TOKEN),
        ],

        # Wrapper for multi-line graph strings.
        'multiline-graph': [
            (r'\"\"\"', String.Double, '#pop'),
            include('graph'),
        ],

        # Wrapper for inline graph strings.
        'inline-graph': [
            (r'\n', Text, '#pop'),
            include('graph')
        ],

        # Provides entry points for the other Jinja2 sections.
        'jinja2-openers': [
            (r'\{\{', Comment.Preproc, 'jinja2-inline'),
            (r'\{\%', Comment.Preproc, 'jinja2-block'),
            # Capture "{#" (jinja2) but not "${#" (bash).
            (r'(?<!\$)\{#', Comment.Multi, 'jinja2-comment'),
        ],

        #  {# ... #}
        'jinja2-comment': [
            (r'#\}', Comment.Multi, '#pop'),
            (r'(.|\n)', Comment.Multi)
        ],

        #  {% ... %}
        'jinja2-block': [
            (r'\%\}', Comment.Preproc, '#pop'),
            (r'(.|\n)', Comment.Preproc)
        ],

        #  {{ ... }}
        'jinja2-inline': [
            (r'\}\}', Comment.Preproc, '#pop'),
            (r'(.|\n)', Comment.Preproc)
        ]

    }


class CylcGraphLexer(CylcLexer):
    """Pygments lexer for Cylc graph strings."""

    tokens = dict(CylcLexer.tokens)
    tokens['root'] = list(tokens['graph'])

    name = 'Cylc Graph'
    aliases = ['cylc-graph']
    filenames = []


def setup(app):
    """Sphinx plugin setup function."""
    app.add_lexer('cylc', CylcLexer())
    app.add_lexer('cylc-graph', CylcGraphLexer())
