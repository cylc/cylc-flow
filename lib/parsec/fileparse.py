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
"""
parsec config file parsing:

 1) inline include-files
 2) process with Jinja2
 3) join continuation lines
 4) parse items into a nested ordered dict
    * line-comments and blank lines are skipped
    * trailing comments are stripped from section headings
    * item value processing:
      - original quoting is retained
      - trailing comments are retained
      (distinguishing between strings and string lists, with all quoting
      and commenting options, is easier during validation when the item
      value type is known).
"""

import os
import sys
import re

from parsec import LOG
from parsec.exceptions import ParsecError, FileParseError
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.include import inline
from parsec.util import itemstr


# heading/sections can contain commas (namespace name lists) and any
# regex pattern characters (this was for pre cylc-6 satellite tasks).
# Proper task names are checked later in config.py.
_HEADING = re.compile(
    r'''^
    (\s*)                     # 1: indentation
    ((?:\[)+)                 # 2: section marker open
    \s*
    (.+?)                     # 3: section name
    \s*
    ((?:\])+)                 # 4: section marker close
    \s*(\#.*)?                # 5: optional trailing comment
    $''',
    re.VERBOSE)

_KEY_VALUE = re.compile(
    r'''^
    (\s*)                   # indentation
    ([.\-\w ,]+?(\s*<.*?>)?)  # key with optional parameters, e.g. foo<m,n>
    \s*=\s*                 # =
    (.*)                    # value (quoted any style + comment)
    $   # line end
    ''',
    re.VERBOSE)

# Designed to match lines ending '\ ' without matching '\   comment'
_BAD_CONTINUATION_TRAILING_WHITESPACE = re.compile(
    r'^([^#\n]+)?\\\s+$', re.VERBOSE)

# quoted value regex reference:
#   http://stackoverflow.com/questions/5452655/
#       python-regex-to-match-text-in-single-quotes-
#           ignoring-escaped-quotes-and-tabs-n

_LINECOMMENT = re.compile(r'^\s*#')
_BLANKLINE = re.compile(r'^\s*$')

# triple quoted values on one line
_SINGLE_LINE_SINGLE = re.compile(r"^'''(.*?)'''\s*(#.*)?$")
_SINGLE_LINE_DOUBLE = re.compile(r'^"""(.*?)"""\s*(#.*)?$')
_MULTI_LINE_SINGLE = re.compile(r"^(.*?)'''\s*(#.*)?$")
_MULTI_LINE_DOUBLE = re.compile(r'^(.*?)"""\s*(#.*)?$')

_TRIPLE_QUOTE = {
    "'''": (_SINGLE_LINE_SINGLE, _MULTI_LINE_SINGLE),
    '"""': (_SINGLE_LINE_DOUBLE, _MULTI_LINE_DOUBLE),
}


def _concatenate(lines):
    """concatenate continuation lines"""
    index = 0
    clines = []
    maxline = len(lines)
    while index < maxline:
        line = lines[index]
        # Raise an error if line has a whitespace after the line break
        if re.match(_BAD_CONTINUATION_TRAILING_WHITESPACE, line):
            msg = ("Syntax error line {0}: Whitespace after the line "
                   "continuation character (\\).")
            raise FileParseError(msg.format(index + 1))
        while line.endswith('\\'):
            if index == maxline - 1:
                # continuation char on the last line
                # must be an error - safe to strip it
                line = line[:-1]
            else:
                index += 1
                line = line[:-1] + lines[index]
        clines.append(line)
        index += 1
    return clines


def addsect(cfig, sname, parents):
    """Add a new section to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]
    if sname in cfig:
        # this doesn't warrant a warning unless contained items are repeated
        LOG.debug(
            'Section already encountered: %s', itemstr(parents + [sname]))
    else:
        cfig[sname] = OrderedDictWithDefaults()


def addict(cfig, key, val, parents, index):
    """Add a new [parents...]key=value pair to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]

    if not isinstance(cfig, dict):
        # an item of this name has already been encountered at this level
        raise FileParseError(
            'line %d: already encountered %s',
            index, itemstr(parents, key, val))

    if key in cfig:
        # this item already exists
        if (key == 'graph' and (
                parents == ['scheduling', 'dependencies'] or
                len(parents) == 3 and
                parents[-3:-1] == ['scheduling', 'dependencies'])):
            # append the new graph string to the existing one
            LOG.debug('Merging graph strings under %s', itemstr(parents))
            if not isinstance(cfig[key], list):
                cfig[key] = [cfig[key]]
            cfig[key].append(val)
        else:
            # otherwise override the existing item
            LOG.debug(
                'overriding %s old value: %s new value: %s',
                itemstr(parents, key), cfig[key], val)
            cfig[key] = val
    else:
        cfig[key] = val


def multiline(flines, value, index, maxline):
    """Consume lines for multiline strings."""
    o_index = index
    quot = value[:3]
    newvalue = value[3:]

    # could be a triple-quoted single line:
    single_line = _TRIPLE_QUOTE[quot][0]
    multi_line = _TRIPLE_QUOTE[quot][1]
    mat = single_line.match(value)
    if mat:
        return value, index
    elif newvalue.find(quot) != -1:
        # TODO - this should be handled by validation?:
        # e.g. non-comment follows single-line triple-quoted string
        raise FileParseError('Invalid line', o_index, flines[index])

    while index < maxline:
        index += 1
        newvalue += '\n'
        line = flines[index]
        if line.find(quot) == -1:
            newvalue += line
        else:
            # end of multiline, process it
            break
    else:
        raise FileParseError(
            'Multiline string not closed', o_index, flines[o_index])

    mat = multi_line.match(line)
    if not mat:
        # e.g. end multi-line string followed by a non-comment
        raise FileParseError('Invalid line', o_index, line)

    # value, comment = mat.groups()
    return quot + newvalue + line, index


def read_and_proc(fpath, template_vars=None, viewcfg=None, asedit=False):
    """
    Read a cylc parsec config file (at fpath), inline any include files,
    process with Jinja2, and concatenate continuation lines.
    Jinja2 processing must be done before concatenation - it could be
    used to generate continuation lines.
    """
    fdir = os.path.dirname(fpath)

    # Allow Python modules in lib/python/ (e.g. for use by Jinja2 filters).
    suite_lib_python = os.path.join(fdir, "lib", "python")
    if os.path.isdir(suite_lib_python) and suite_lib_python not in sys.path:
        sys.path.append(suite_lib_python)

    LOG.debug('Reading file %s', fpath)

    # read the file into a list, stripping newlines
    with open(fpath) as f:
        flines = [line.rstrip('\n') for line in f]

    do_inline = True
    do_empy = True
    do_jinja2 = True
    do_contin = True
    if viewcfg:
        if not viewcfg['empy']:
            do_empy = False
        if not viewcfg['jinja2']:
            do_jinja2 = False
        if not viewcfg['contin']:
            do_contin = False
        if not viewcfg['inline']:
            do_inline = False

    # inline any cylc include-files
    if do_inline:
        flines = inline(
            flines, fdir, fpath, False, viewcfg=viewcfg, for_edit=asedit)

    # process with EmPy
    if do_empy:
        if flines and re.match(r'^#![Ee]m[Pp]y\s*', flines[0]):
            LOG.debug('Processing with EmPy')
            try:
                from parsec.empysupport import empyprocess
            except (ImportError, ModuleNotFoundError):
                raise ParsecError('EmPy Python package must be installed '
                                  'to process file: ' + fpath)
            flines = empyprocess(flines, fdir, template_vars)

    # process with Jinja2
    if do_jinja2:
        if flines and re.match(r'^#![jJ]inja2\s*', flines[0]):
            LOG.debug('Processing with Jinja2')
            try:
                from parsec.jinja2support import jinja2process
            except (ImportError, ModuleNotFoundError):
                raise ParsecError('Jinja2 Python package must be installed '
                                  'to process file: ' + fpath)
            flines = jinja2process(flines, fdir, template_vars)

    # concatenate continuation lines
    if do_contin:
        flines = _concatenate(flines)

    # return rstripped lines
    return [fl.rstrip() for fl in flines]


def parse(fpath, output_fname=None, template_vars=None):
    """Parse file items line-by-line into a corresponding nested dict."""

    # read and process the file (jinja2, include-files, line continuation)
    flines = read_and_proc(fpath, template_vars)
    if output_fname:
        with open(output_fname, 'w') as handle:
            handle.write('\n'.join(flines) + '\n')
        LOG.debug('Processed configuration dumped: %s', output_fname)

    nesting_level = 0
    config = OrderedDictWithDefaults()
    parents = []

    maxline = len(flines) - 1
    index = -1

    while index < maxline:
        index += 1
        line = flines[index]

        if re.match(_LINECOMMENT, line):
            # skip full-line comments
            continue

        if re.match(_BLANKLINE, line):
            # skip blank lines
            continue

        m = re.match(_HEADING, line)
        if m:
            # matched a section heading
            s_open, sect_name, s_close = m.groups()[1:-1]
            nb = len(s_open)

            if nb != len(s_close):
                raise FileParseError('bracket mismatch', index, line)
            elif nb == nesting_level:
                # sibling section
                parents = parents[:-1] + [sect_name]
            elif nb == nesting_level + 1:
                # child section
                parents = parents + [sect_name]
            elif nb < nesting_level:
                # back up one or more levels
                ndif = nesting_level - nb
                parents = parents[:-ndif - 1] + [sect_name]
            else:
                raise FileParseError(
                    'Error line ' + str(index + 1) + ': ' + line)
            nesting_level = nb
            addsect(config, sect_name, parents[:-1])

        else:
            m = re.match(_KEY_VALUE, line)
            if m:
                # matched a key=value item
                key, _, val = m.groups()[1:]
                if val.startswith('"""') or val.startswith("'''"):
                    # triple quoted - may be a multiline value
                    val, index = multiline(flines, val, index, maxline)
                addict(config, key, val, parents, index)
            else:
                # no match
                raise FileParseError(
                    'Invalid line ' + str(index + 1) + ': ' + line)

    return config
