#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys, re

from OrderedDict import OrderedDict
from include import inline, IncludeFileNotFoundError
from util import itemstr
import cylc.flags

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

try:
    from Jinja2Support import Jinja2Process, TemplateError, TemplateSyntaxError
except ImportError:
    jinja2_disabled = True
else:
    jinja2_disabled = False

# heading/sections can contain commas (namespace name lists) and any
# regex pattern characters - for ASYNCID tasks. Proper task names are
# checked later in config.py.
_HEADING = re.compile(r'''^
    (\s*)                     # 1: indentation
    ((?:\[)+)                 # 2: section marker open
    \s*
    (.+?)                     # 3: section name
    \s*
    ((?:\])+)                 # 4: section marker close
    \s*(\#.*)?                # 5: optional trailing comment
    $''',
    re.VERBOSE)

_KEY_VALUE = re.compile(r'''^
    (\s*)                   # indentation
    ([\.\-\w \,]+?)         # key
    \s*=\s*                 # =
    (.*)                    # value (quoted any style + comment)
    $   # line end
    ''',
    re.VERBOSE)

# quoted value regex reference:
#   http://stackoverflow.com/questions/5452655/
#       python-regex-to-match-text-in-single-quotes-ignoring-escaped-quotes-and-tabs-n

_LINECOMMENT = re.compile( '^\s*#' )
_BLANKLINE = re.compile( '^\s*$' )

# triple quoted values on one line
_SINGLE_LINE_SINGLE = re.compile(r"^'''(.*?)'''\s*(#.*)?$")
_SINGLE_LINE_DOUBLE = re.compile(r'^"""(.*?)"""\s*(#.*)?$')
_MULTI_LINE_SINGLE = re.compile(r"^(.*?)'''\s*(#.*)?$")
_MULTI_LINE_DOUBLE = re.compile(r'^(.*?)"""\s*(#.*)?$')

_TRIPLE_QUOTE = {
    "'''": (_SINGLE_LINE_SINGLE, _MULTI_LINE_SINGLE),
    '"""': (_SINGLE_LINE_DOUBLE, _MULTI_LINE_DOUBLE),
}

class ParseError( Exception ):
    def __init__( self, reason, index=None, line=None ):
        self.msg = "ParseError: " + reason
        if index:
            self.msg += " (line " + str(index+1) + ")"
        if line:
            self.msg += ":\n   " + line.strip()
        if index:
            # TODO - make 'view' function independent of cylc:
            self.msg += "\n(line numbers match 'cylc view -p')"
    def __str__( self ):
        return self.msg

class FileNotFoundError( ParseError ):
    pass

def _concatenate( lines ):
    """concatenate continuation lines"""
    index = 0
    clines = []
    maxline = len(lines)
    while index < maxline:
        line = lines[index]
        while line.endswith('\\'):
            if index == maxline-1:
                # continuation char on the last line
                # must be an error - safe to strip it
                line = line[:-1]
            else:
                index += 1
                line = line[:-1] + lines[index]
        clines.append(line)
        index +=1
    return clines

def addsect( cfig, sname, parents ):
    """Add a new section to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]
    if sname in cfig:
        # this doesn't warrant a warning unless contained items are repeated
        if cylc.flags.verbose:
            print 'Section already encountered: ' + itemstr( parents + [sname] )
    else:
        cfig[sname] = OrderedDict()

def addict( cfig, key, val, parents, index ):
    """Add a new [parents...]key=value pair to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]

    if not isinstance( cfig, dict ):
        # an item of this name has already been encountered at this level
        print >> sys.stderr, itemstr( parents, key, val )
        raise ParseError( 'ERROR line ' + str(index) + ': already encountered ' + itemstr( parents ))

    if key in cfig:
        # this item already exists
        if key == 'graph' and \
                ( len( parents ) == 2 and parents == ['scheduling','dependencies'] or \
                len( parents ) == 3 and parents[-3:-1] == ['scheduling','dependencies'] ):
            # append the new graph string to the existing one
           if cylc.flags.verbose:
               print 'Merging graph strings under ' + itemstr( parents )
           if not isinstance( cfig[key], list ):
               cfig[key] = [cfig[key]]
           cfig[key].append(val)
        else:
            # otherwise override the existing item
            if cylc.flags.verbose:
                print >> sys.stderr, 'WARNING: overriding ' + itemstr( parents, key )
                print >> sys.stderr, ' old value: ' + cfig[key]
                print >> sys.stderr, ' new value: ' + val
            cfig[key] = val
    else:
        cfig[key] = val


def multiline( flines, value, index, maxline ):
    """Consume lines for multiline strings."""
    o_index = index
    quot = value[:3]
    newvalue = value[3:]

    # could be a triple-quoted single line:
    single_line = _TRIPLE_QUOTE[quot][0]
    multi_line = _TRIPLE_QUOTE[quot][1]
    mat = single_line.match(value)
    if mat:
        val, comment = list(mat.groups())
        return value, index
    elif newvalue.find(quot) != -1:
        # TODO - this should be handled by validation?:
        # e.g. non-comment follows single-line triple-quoted string
        raise ParseError( 'Invalid line', o_index, flines[index] )

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
        raise ParseError( 'Multiline string not closed', o_index, flines[o_index] )

    mat = multi_line.match(line)
    if not mat:
        # e.g. end multi-line string followed by a non-comment
        raise ParseError( 'Invalid line', o_index, line )

    #value, comment = mat.groups()
    return quot + newvalue + line, index

def read_and_proc( fpath, template_vars=[], template_vars_file=None, viewcfg=None, asedit=False ):
    """
    Read a cylc parsec config file (at fpath), inline any include files,
    process with Jinja2, and concatenate continuation lines.
    Jinja2 processing must be done before concatenation - it could be
    used to generate continuation lines.
    """
    if not os.path.isfile( fpath ):
        raise FileNotFoundError, 'File not found: ' + fpath

    if cylc.flags.verbose:
        print "Reading file", fpath

    # read the file into a list, stripping newlines
    with open( fpath ) as f:
        flines = [ line.rstrip('\n') for line in f ]

    fdir = os.path.dirname(fpath)

    do_inline = True
    do_jinja2 = True
    do_contin = True
    if viewcfg:
        if not viewcfg['jinja2']:
            do_jinja2 = False
        if not viewcfg['contin']:
            do_contin = False
        if not viewcfg['inline']:
            do_inline = False

    # inline any cylc include-files
    if do_inline:
        try:
            flines = inline( flines, fdir, fpath, False, viewcfg=viewcfg, for_edit=asedit )
        except IncludeFileNotFoundError, x:
            raise ParseError( str(x) )

    # process with Jinja2
    if do_jinja2:
        if flines and re.match( '^#![jJ]inja2\s*', flines[0] ):
            if jinja2_disabled:
                raise ParseError( 'Jinja2 is not installed' )
            if cylc.flags.verbose:
                print "Processing with Jinja2"
            try:
                flines = Jinja2Process( flines, fdir,
                        template_vars, template_vars_file )
            except TemplateSyntaxError, x:
                lineno = x.lineno + 1  # (flines array starts from 0)
                msg = "Jinja2 Syntax Error (line " + str(lineno) + ")"
                msg += "\n   " + flines[x.lineno].strip()
                # TODO - make "view" function independent of cylc:
                msg += "\n(line numbers match 'cylc view -i')"
                raise ParseError(msg)
            except TemplateError, x:
                print >> sys.stderr, 'Jinja2 Template Error:', x
                raise ParseError(repr(x))
            except TypeError, x:
                print >> sys.stderr, 'Jinja2 Type Error:', x
                raise ParseError(repr(x))

    # concatenate continuation lines
    if do_contin:
        flines = _concatenate( flines )

    # return rstripped lines
    return [ fl.rstrip() for fl in flines ]

def parse( fpath, write_proc=False,
        template_vars=[], template_vars_file=None ):
    "Parse file items line-by-line into a corresponding nested dict."

    # read and process the file (jinja2, include-files, line continuation)
    flines = read_and_proc( fpath, template_vars, template_vars_file )
    # write the processed for suite.rc if it lives in a writable directory
    if write_proc and \
            os.access(os.path.dirname(fpath), os.W_OK):
        fpath_processed = fpath + '.processed'
        if cylc.flags.verbose:
            print "Writing file " + fpath_processed
        f = open( fpath_processed, 'w' )
        f.write('\n'.join(flines))
        f.close()

    nesting_level = 0
    config = OrderedDict()
    sect_name = None
    parents = []

    maxline = len(flines)-1
    index = -1

    while index < maxline:
        index += 1
        line = flines[index]

        if re.match( _LINECOMMENT, line ):
            # skip full-line comments
            continue

        if re.match( _BLANKLINE, line ):
            # skip blank lines
            continue

        m = re.match( _HEADING, line )
        if m:
            # matched a section heading
            indent, s_open, sect_name, s_close, comment = m.groups()
            nb = len(s_open)

            if nb != len(s_close):
                raise ParseError('bracket mismatch', index, line )
            elif nb == nesting_level:
                # sibling section
                parents = parents[:-1] + [sect_name]
            elif nb == nesting_level + 1:
                # child section
                parents = parents + [sect_name]
            elif nb < nesting_level:
                # back up one or more levels
                ndif = nesting_level -nb
                parents = parents[:-ndif-1] + [sect_name]
            else:
                raise ParseError( 'Error line ' + str(index+1) + ': ' + line )
            nesting_level = nb
            addsect( config, sect_name, parents[:-1] )

        else:
            m = re.match( _KEY_VALUE, line )
            if m:
                # matched a key=value item
                indent, key, val = m.groups()
                if val.startswith('"""') or val.startswith("'''"):
                    # triple quoted - may be a multiline value
                    val, index = multiline( flines, val, index, maxline )
                addict( config, key, val, parents, index )
            else:
                # no match
                raise ParseError( 'Invalid line ' + str(index+1) + ': ' + line )

    return config

