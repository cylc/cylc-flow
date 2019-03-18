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

"""An extension providing pygments lexers for suite.rc files and Cylc graph
strings."""

from pygments.lexer import RegexLexer, bygroups, include
from pygments.token import (Name, Comment, Text, Operator, String,
                            Punctuation, Error, Keyword, Other)


class CylcLexer(RegexLexer):
    """Pygments lexer for the Cylc suite.rc language."""

    # Pygments tokens for Cylc suite.rc elements which have no direct
    # translation.
    HEADING_TOKEN = Name.Tag
    SETTING_TOKEN = Name.Variable
    GRAPH_TASK_TOKEN = Keyword.Declaration
    GRAPH_XTRIGGER_TOKEN = Keyword.Type
    PARAMETERISED_TASK_TOKEN = Name.Builtin
    EXTERNAL_SUITE_TOKEN = Name.Builtin.Pseudo
    INTERCYCLE_OFFSET_TOKEN = Name.Builtin

    EMPY_BLOCK_REGEX = r'@\{([^\{\}]+|\{[^\}]+\})+\}'
    EMPY_BLOCK_REGEX = (
        r'@\%(open)s('  # open empy block
        r'[^\%(open)s\%(close)s]+|'  # either not a close character
        r'\%(open)s([^\%(close)s]+)?\%(close)s)+'  # or permit 1 level nesting
        r'\%(close)s')  # close empy block

    # Pygments values.
    name = 'Cylc'
    aliases = ['cylc', 'suiterc']
    filenames = ['suite.rc']
    # mimetypes = ['text/x-ini', 'text/inf']

    # Patterns, rules and tokens.
    tokens = {
        'root': [
            # Jinja2 opening braces:  {{  {%  {#
            include('preproc'),

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
            (r'([^=\n]+)(=)([\s+])?(\"\"\")',
                bygroups(SETTING_TOKEN,
                         Operator,
                         Text,
                         String.Double), 'multiline-setting'),

            # Inline settings:  key = ...
            (r'([^=\n]+)(=)',
                bygroups(SETTING_TOKEN,
                         Operator), 'setting'),

            # Include files
            (r'(%include)( )(.*)', bygroups(Operator, Text, String)),

            # Arbitrary whitespace
            (r'\s', Text)
        ],

        'heading': [
            (r'[\]]+', HEADING_TOKEN, '#pop'),
            include('preproc'),
            include('parameterisation'),
            (r'(\\\n|.)', HEADING_TOKEN),  # Allow line continuation chars.
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
            include('preproc'),
            (r'\\\n', String),
            (r'.', String),

        ],

        # The value in a key = """value""" pair.
        'multiline-setting': [
            (r'\"\"\"', String.Double, '#pop'),
            include('comment'),
            include('preproc'),
            (r'(\n|.)', String.Double)
        ],

        # Graph strings:  foo => bar & baz
        'graph': [
            include('preproc'),
            include('comment'),
            include('inter-suite-trigger'),
            include('parameterisation'),
            (r'@\w+', GRAPH_XTRIGGER_TOKEN),
            (r'\w+', GRAPH_TASK_TOKEN),
            (r'\!\w+', Other),
            (r'\s', Text),
            (r'=>', Operator),
            (r'[\&\|]', Operator),
            (r'[\(\)]', Punctuation),
            (r'\[', Text, 'intercycle-offset'),
            (r'.', Comment)
        ],

        'inter-suite-trigger': [
            (r'(\<)'
             r'([^\>]+)'  # foreign suite
             r'(::)'
             r'([^\>]+)'  # foreign task
             r'(\>)',
             bygroups(Text, EXTERNAL_SUITE_TOKEN, Text,
                      PARAMETERISED_TASK_TOKEN, Text)),
        ],

        # Parameterised syntax:  <foo=1>
        'parameterisation': [
            (r'(\<)'  # Opening greater-than bracket.
             r'(\s?\w+\s?'  # Parameter name (permit whitespace).
             r'(?:[+-=]\s?\w+)?'  # [+-=] for selecting parameters.
             r'\s?'  # Permit whitespace.
             r'(?:'  # BEGIN optional extra parameter groups...
             r'(?:\s?,\s?\w+\s?'  # Comma separated parameters.
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
             # ..Seconds.
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

        'empy': [
            (r'#![Ee]mpy', Comment.Hashbang),  # #!empy
            (r'@@', Text),  # @@
            # @[...]
            (EMPY_BLOCK_REGEX % {'open': '(', 'close': ')'}, Comment.Preproc),
            # @{...}
            (EMPY_BLOCK_REGEX % {'open': '{', 'close': '}'}, Comment.Preproc),
            # @(...)
            (EMPY_BLOCK_REGEX % {'open': '[', 'close': ']'}, Comment.Preproc),
            (r'@empy\.[\w]+[^\n]+', Comment.Preproc),  # @empy...
            (r'(\s+)?@#.*', Comment.Multi),  # @# ...
            (r'@[\w.]+', Comment.Preproc)  # @...
        ],

        'jinja2': [
            (r'#![Jj]inja2', Comment.Hashbang),  # #!jinja2
            (r'\{\{((.|\n)+?)(?=\}\})\}\}', Comment.Preproc),  # {{...}}
            (r'\{\%((.|\n)+?)(?=\%\})\%\}', Comment.Preproc),  # {%...%}
            (r'\{\#((.|\n)+?)(?=\#\})\#\}', Comment.Multi),  # {#...#}
        ],

        'preproc': [
            include('empy'),
            include('jinja2')
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
