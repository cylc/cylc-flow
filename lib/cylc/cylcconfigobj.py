
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
from configobj import ConfigObj, Section, \
        ConfigObjError, NestingError, ParseError, DuplicateError, UnreprError, UnknownType

class CylcConfigObj( ConfigObj ):
    """ This class overrides the parse() method of ConfigObj in order to
    provide to allow duplicate keywords (variable overriding) in cylc
    config environment and directives sections."""

    def _parse(self, infile):
        """Actually parse the config file."""
        temp_list_values = self.list_values
        if self.unrepr:
            self.list_values = False
            
        comment_list = []
        done_start = False
        this_section = self
        maxline = len(infile) - 1
        cur_index = -1
        reset_comment = False
        
        while cur_index < maxline:
            if reset_comment:
                comment_list = []
            cur_index += 1
            line = infile[cur_index]
            sline = line.strip()
            # do we have anything on the line ?
            if not sline or sline.startswith('#'):
                reset_comment = False
                comment_list.append(line)
                continue
            
            if not done_start:
                # preserve initial comment
                self.initial_comment = comment_list
                comment_list = []
                done_start = True
                
            reset_comment = True
            # first we check if it's a section marker
            mat = self._sectionmarker.match(line)
            if mat is not None:
                # is a section line
                (indent, sect_open, sect_name, sect_close, comment) = mat.groups()
                if indent and (self.indent_type is None):
                    self.indent_type = indent
                cur_depth = sect_open.count('[')
                if cur_depth != sect_close.count(']'):
                    print >> sys.stderr, 'ERROR:', line
                    self._handle_error("Cannot compute the section depth at line %s.",
                                       NestingError, infile, cur_index)
                    continue
                
                if cur_depth < this_section.depth:
                    # the new section is dropping back to a previous level
                    try:
                        parent = self._match_depth(this_section,
                                                   cur_depth).parent
                    except SyntaxError:
                        print >> sys.stderr, 'ERROR:', line
                        self._handle_error("Cannot compute nesting level at line %s.",
                                           NestingError, infile, cur_index)
                        continue
                elif cur_depth == this_section.depth:
                    # the new section is a sibling of the current section
                    parent = this_section.parent
                elif cur_depth == this_section.depth + 1:
                    # the new section is a child the current section
                    parent = this_section
                else:
                    print >> sys.stderr, 'ERROR:', line
                    self._handle_error("Section too nested at line %s.",
                                       NestingError, infile, cur_index)
                    
                sect_name = self._unquote(sect_name)
                if sect_name in parent:
                    print >> sys.stderr, 'ERROR:', line
                    self._handle_error('Duplicate section name at line %s.',
                                       DuplicateError, infile, cur_index)
                    continue
                
                # create the new section
                this_section = Section(
                    parent,
                    cur_depth,
                    self,
                    name=sect_name)
                parent[sect_name] = this_section
                parent.inline_comments[sect_name] = comment
                parent.comments[sect_name] = comment_list
                continue
            #
            # it's not a section marker,
            # so it should be a valid ``key = value`` line
            mat = self._keyword.match(line)
            if mat is None:
                # it neither matched as a keyword
                # or a section marker
                self._handle_error(
                        'Invalid line at line "%s":' + '\n' + line,
                    ParseError, infile, cur_index)
            else:
                # is a keyword value
                # value will include any inline comment
                (indent, key, value) = mat.groups()
                if indent and (self.indent_type is None):
                    self.indent_type = indent
                # check for a multiline value
                if value[:3] in ['"""', "'''"]:
                    try:
                        value, comment, cur_index = self._multiline(
                            value, infile, cur_index, maxline)
                    except SyntaxError:
                        print >> sys.stderr, 'ERROR:', line
                        self._handle_error(
                            'Parse error in value at line %s.',
                            ParseError, infile, cur_index)
                        continue
                    else:
                        if self.unrepr:
                            comment = ''
                            try:
                                value = unrepr(value)
                            except Exception, e:
                                if type(e) == UnknownType:
                                    msg = 'Unknown name or type in value at line %s.'
                                else:
                                    msg = 'Parse error in value at line %s.'
                                print >> sys.stderr, 'ERROR:', line
                                self._handle_error(msg, UnreprError, infile,
                                    cur_index)
                                continue
                else:
                    if self.unrepr:
                        comment = ''
                        try:
                            value = unrepr(value)
                        except Exception, e:
                            if isinstance(e, UnknownType):
                                msg = 'Unknown name or type in value at line %s.'
                            else:
                                msg = 'Parse error in value at line %s.'
                            print >> sys.stderr, 'ERROR:', line
                            self._handle_error(msg, UnreprError, infile,
                                cur_index)
                            continue
                    else:
                        # extract comment and lists
                        try:
                            (value, comment) = self._handle_value(value)
                        except SyntaxError:
                            print >> sys.stderr, 'ERROR:', line
                            self._handle_error(
                                'Parse error in value at line %s.',
                                ParseError, infile, cur_index)
                            continue
                #
                key = self._unquote(key)
                if key in this_section:
                    # CYLC CHANGE START: ALLOW DUPLICATE KEYWORDS TO OVERRIDE
                    # PREVIOUS VALUES IN 'environment' AND 'directives' SECTIONS.
                    envoverride = False
                    try:
                        if sect_name == 'environment' or sect_name == 'directives':
                            print >> sys.stderr, 'WARNING: $' + key + ' redefined (line ' + str(cur_index) + ')'
                            envoverride = True
                    except UnboundLocalError:
                        # not in a section yet, pass on to handle error
                        pass
                    if not envoverride:
                        print >> sys.stderr, 'ERROR:', line
                        self._handle_error(
                                'Duplicate keyword name at line %s.',
                                DuplicateError, infile, cur_index)
                        continue
                    else: # envoverride = True
                        # delete the existing item before inserting the new
                        # one - otherwise the new one does override, but
                        # it ends up in the position of the old one!
                        this_section.__delitem__(key)

                    # CYLC change END
                # add the key.
                # we set unrepr because if we have got this far we will never
                # be creating a new section
                this_section.__setitem__(key, value, unrepr=True)
                this_section.inline_comments[key] = comment
                this_section.comments[key] = comment_list
                continue
        #
        if self.indent_type is None:
            # no indentation used, set the type accordingly
            self.indent_type = ''

        # preserve the final comment
        if not self and not self.initial_comment:
            self.initial_comment = comment_list
        elif not reset_comment:
            self.final_comment = comment_list
        self.list_values = temp_list_values


