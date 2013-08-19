#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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
from cylc.include_files import inline, IncludeFileError

"""
Module to parse a cylc parsec config file into a nested ordered dict.
"""

try:
    from cylc.Jinja2Support import Jinja2Process, TemplateError, TemplateSyntaxError
except ImportError:
    jinja2_disabled = True
else:
    jinja2_disabled = False

# heading/sections can contain commas (namespace name lists) and any
# regex pattern characters - for ASYNCID tasks. Proper task names are
# checked later in config.py.
_HEADING = re.compile(r'''^
    (\s*)                     # 1: indentation
    ((?:\[\s*)+)              # 2: section marker open
    (.+?)                     # 3: section name
    ((?:\s*\])+)              # 4: section marker close
    \s*(\#.*)?                # 5: optional comment
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

# single-quoted value and trailing string (checked for comment below)

# BROKEN: CANNOT HAVE BACKREFERENCE IN CHARACTER CLASS []
BROKEN_SQ_VALUE = re.compile( 
r"""
    ('|")            # 1: opening quote
    (                # 2: string contents
      [^\1\\]*            # zero or more non-quote, non-backslash
      (?:                 # "unroll-the-loop"!
        \\.               # allow escaped anything.
        [^\1\\]*          # zero or more non-quote, non-backslash
      )*                  # finish {(special normal*)*} construct.
    )                     # end string contents.
    \1             # 3: closing quote
    (?:\s*\#.*)?$    # optional trailing comment
    """, re.VERBOSE )

_SQ_VALUE = re.compile( 
r"""
    (?:'            # opening quote
    (                # 1: string contents
      [^'\\]*            # zero or more non-quote, non-backslash
      (?:                 # "unroll-the-loop"!
        \\.               # allow escaped anything.
        [^'\\]*          # zero or more non-quote, non-backslash
      )*                  # finish {(special normal*)*} construct.
    )                     # end string contents.
    ')             # closing quote
    (?:\s*\#.*)?$    # optional trailing comment
    """, re.VERBOSE )

_DQ_VALUE = re.compile( 
r"""
    (?:"            # opening quote
    (                # 1: string contents
      [^"\\]*            # zero or more non-quote, non-backslash
      (?:                 # "unroll-the-loop"!
        \\.               # allow escaped anything.
        [^"\\]*          # zero or more non-quote, non-backslash
      )*                  # finish {(special normal*)*} construct.
    )                     # end string contents.
    ")             # closing quote
    (?:\s*\#.*)?$    # optional trailing comment
    """, re.VERBOSE )


# unquoted value with optional trailing comment
_UQ_VALUE = re.compile( '^(.*?)(\s*\#.*)?$' )

_LINECOMMENT = re.compile( '^\s*#' )
_BLANKLINE = re.compile( '^\s*$' )

# regexes for finding triple quoted values on one line
_SINGLE_LINE_SINGLE = re.compile(r"^'''(.*?)'''\s*(#.*)?$")
_SINGLE_LINE_DOUBLE = re.compile(r'^"""(.*?)"""\s*(#.*)?$')
_MULTI_LINE_SINGLE = re.compile(r"^(.*?)'''\s*(#.*)?$")
_MULTI_LINE_DOUBLE = re.compile(r'^(.*?)"""\s*(#.*)?$')

_TRIPLE_QUOTE = {
    "'''": (_SINGLE_LINE_SINGLE, _MULTI_LINE_SINGLE),
    '"""': (_SINGLE_LINE_DOUBLE, _MULTI_LINE_DOUBLE),
}


class ParseError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

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

def _single_unquote(value):
    """Return an unquoted version of a single-quoted value"""
    if (value[0] == value[-1]) and (value[0] in ('"', "'")):
        value = value[1:-1]
    return value

def addsect( cfig, sname, parents, verbose ):
    """Add a new section to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]
    if sname in cfig:
        # this doesn't warrant a warning unless contained items are repeated
        if verbose:
            print 'Section [' + ']['.join(parents + [sname]) + '] already encountered'
    else:
        cfig[sname] = OrderedDict()

def addict( cfig, key, val, parents, verbose ):
    """Add a new [parents...]key=value pair to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]
    if key in cfig:
        # already defined - ok for graph strings
        if key == 'graph' and set(parents[:-1]) == set(['scheduling','dependencies']):
            try:
                cfig[key] += '\n' + val
            except IndexError:
                # no graph string
                pass
            else:
                if verbose:
                    print 'Merging graph strings under [' + ']['.join(parents) + ']'
        else:
            if verbose:
                print >> sys.stderr, 'WARNING: overriding [' + ']['.join(parents) + ']' + key
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
    if mat is not None:
        val, comment = list(mat.groups())
        return val, index
    elif newvalue.find(quot) != -1:
        raise ParseError('Unbalanced quote problem near line ' + str(o_index+1) + ' ?')

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
        # we've got to the end of the config, oops...
        raise ParseError( 'Multiline string at ' + str(o_index+1) + ' hit EOF' )
    mat = multi_line.match(line)
    if mat is None:
        # a badly formed line
        print >> sys.stderr, line
        raise ParseError( 'Badly formed line at ' + str(o_index+1) + '?')
    value, comment = mat.groups()
    return newvalue + value, index


def read_and_proc( fpath, verbose=False, template_vars=[], template_vars_file=None, viewcfg=None ):
    """
    Read a cylc parsec config file (at fpath), inline any include files,
    process with Jinja2, and concatenate continuation lines.
    Jinja2 processing must be done before concatenation - it could be
    used to generate continuation lines.
    """
    if not os.path.isfile( fpath ):
        raise FileNotFoundError, 'File not found: ' + fpath

    if verbose:
        print "Reading file", fpath

    # read the file into a list, stripping newlines
    f = open( fpath, 'r' )
    flines = [ line.rstrip('\n') for line in f ]
    f.close()

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
            flines = inline( flines, fdir, False, viewcfg=viewcfg )
        except IncludeFileError, x:
            raise ParseError( str(x) )

    # process with Jinja2
    if do_jinja2:
        if flines and re.match( '^#![jJ]inja2\s*', flines[0] ):
            if jinja2_disabled:
                raise ParseError( 'Jinja2 is not installed' )
            if verbose:
                print "Processing with Jinja2"
            try:
                flines = Jinja2Process( flines, fdir,
                        template_vars, template_vars_file, verbose )
            except TemplateSyntaxError, x:
                lineno = x.lineno + 1  # (flines array starts from 0)
                print >> sys.stderr, 'Jinja2 Template Syntax Error, line', lineno
                print >> sys.stderr, flines[x.lineno]
                raise ParseError(str(x))
            except TemplateError, x:
                print >> sys.stderr, 'Jinja2 Template Error'
                raise ParseError(x)
            except TypeError, x:
                print >> sys.stderr, 'Jinja2 Type Error'
                raise ParseError(x)

    # concatenate continuation lines
    if do_contin:
        flines = _concatenate( flines )

    return flines

def parse( fpath, verbose=False,
        template_vars=[], template_vars_file=None ):
    """
    Parse a nested config file and return a corresponding nested dict.
    """
    # read and process the file (jinja2, include-files, line continuation)
    flines = read_and_proc( fpath, verbose, 
            template_vars, template_vars_file )
    # write the processed 
    if fpath.endswith("suite.rc"):
        fp = fpath + '.processed'
        if verbose:
            print "Writing file" + fp
        f = open( fp, 'w' )
        f.write('\n'.join(flines))
        f.close()

    nesting_level = 0
    config = OrderedDict()
    sect_name = None
    parents = []

    maxline = len(flines)-1
    index = -1

    # parse file lines one-by-one
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
            s_open = s_open.strip()
            s_close = s_close.strip()
            nb = len(s_open)

            if nb != len(s_close):
                print >> sys.stderr, line
                raise ParseError('Section bracket mismatch, line ' + str(index+1))
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
                print >> sys.stderr, line
                raise ParseError( 'Section nesting error, line ' + str(index+1))
            nesting_level = nb
            addsect( config, sect_name, parents[:-1], verbose )

        else:
            m = re.match( _KEY_VALUE, line )
            if m:
                # matched a key=value item
                indent, key, val = m.groups()
                if not val:
                    # empty value - same as item not present
                    continue
                if val[:3] in ['"""', "'''"]:
                    # triple quoted - may be a multiline value
                    val, index = multiline( flines, val, index, maxline )
                else:
                    m = re.match( _SQ_VALUE, val )
                    if m:
                        # single quoted value: unquote and strip comment
                        val = m.groups()[0]
                        #print 'SINGLE      ', key, ' = ', val
                    else:
                        m = re.match( _DQ_VALUE, val )
                        if m:
                            # double quoted value: unquote and strip comment
                            val = m.groups()[0]
                            #print 'DOUBLE      ', key, ' = ', val
                        elif val[0] in ["'", '"']:
                            # must be a quoted list: unquote and strip comment
                            #print 'QUOTED LIST ', key, ' = ', val
                            if val[0] == "'":
                                reg = _SQ_VALUE
                            else:
                                reg = _DQ_VALUE
                            vals = re.split( '\s*,\s*', val )
                            val = ''
                            for v in vals:
                                m = re.match(reg, v)
                                if m:
                                    val += m.groups()[0] + ','
                            val = val.rstrip(',')
                        else:
                            m = re.match( _UQ_VALUE, val )
                            if m:
                                # unquoted value: strip comment
                                val = m.groups()[0]
                                #print 'UNQUOTED    ', key, ' = ', val
                            else:
                                print >> sys.stderr, line
                                raise ParseError( 'Invalid line (1) at ' + str(index+1) )
                addict( config, key, val, parents, verbose )
            else:
                # no match
                print >> sys.stderr, line
                raise ParseError( 'Invalid line (2) at line ' + str(index+1) )
    return config

