
import os, re
from configobj import ConfigObj, Section, \
        ConfigObjError, NestingError, ParseError, DuplicateError, UnreprError, UnknownType

class CylcConfigObj( ConfigObj ):
    """ This class overrides the _load() and parse() menthods of ConfigObj in 
    order to provide: continuation lines and include files (_load) and to 
    allow duplicate keywords (variable overriding) in cylc config
    [environment] sections (parse). The class methods involved here are
    quite long but the cylc code changes in them are quite small."""

    def _load(self, infile, configspec):
        if isinstance(infile, basestring):
            self.filename = infile
            if os.path.isfile(infile):
                # cylc suite dir:
                self.suite_dir = os.path.dirname( infile )
                h = open(infile, 'rb')
                # cylc: this reads into a single line
                #infile = h.read() or []
                # cylc: read into a list for line-by-line processing
                infile = h.readlines()
                h.close()

                infile = self.include_files( infile )
                infile = self.continuation_lines( infile )
                #check:
                #for line in infile:
                #    print line,
                # cylc: apparently it is not necessary to join back into a single string
            elif self.file_error:
                # raise an error if the file doesn't exist
                raise IOError('Config file not found: "%s".' % self.filename)
            else:
                # file doesn't already exist
                if self.create_empty:
                    # this is a good test that the filename specified
                    # isn't impossible - like on a non-existent device
                    h = open(infile, 'w')
                    h.write('')
                    h.close()
                infile = []
                
        elif isinstance(infile, (list, tuple)):
            infile = list(infile)
            
        elif isinstance(infile, dict):
            # initialise self
            # the Section class handles creating subsections
            if isinstance(infile, ConfigObj):
                # get a copy of our ConfigObj
                def set_section(in_section, this_section):
                    for entry in in_section.scalars:
                        this_section[entry] = in_section[entry]
                    for section in in_section.sections:
                        this_section[section] = {}
                        set_section(in_section[section], this_section[section])
                set_section(infile, self)
                
            else:
                for entry in infile:
                    self[entry] = infile[entry]
            del self._errors
            
            if configspec is not None:
                self._handle_configspec(configspec)
            else:
                self.configspec = None
            return
        
        elif getattr(infile, 'read', MISSING) is not MISSING:
            # This supports file like objects
            infile = infile.read() or []
            # needs splitting into lines - but needs doing *after* decoding
            # in case it's not an 8 bit encoding
        else:
            raise TypeError('infile must be a filename, file like object, or list of lines.')
        
        if infile:
            # don't do it for the empty ConfigObj
            infile = self._handle_bom(infile)
            # infile is now *always* a list
            #
            # Set the newlines attribute (first line ending it finds)
            # and strip trailing '\n' or '\r' from lines
            for line in infile:
                if (not line) or (line[-1] not in ('\r', '\n', '\r\n')):
                    continue
                for end in ('\r\n', '\n', '\r'):
                    if line.endswith(end):
                        self.newlines = end
                        break
                break

            infile = [line.rstrip('\r\n') for line in infile]
            
        self._parse(infile)
        # if we had any errors, now is the time to raise them
        if self._errors:
            info = "at line %s." % self._errors[0].line_number
            if len(self._errors) > 1:
                msg = "Parsing failed with several errors.\nFirst error %s" % info
                error = ConfigObjError(msg)
            else:
                error = self._errors[0]
            # set the errors attribute; it's a list of tuples:
            # (error_type, message, line_number)
            error.errors = self._errors
            # set the config attribute
            error.config = self
            raise error
        # delete private attributes
        del self._errors
        
        if configspec is None:
            self.configspec = None
        else:
            self._handle_configspec(configspec)
    
    def include_files( self, inf ):
        outf = []
        for line in inf:
            m = re.match( '\s*%include\s+([\w/\.\-]+)\s*$', line )
            if m:
                match = m.groups()[0]
                inc = os.path.join( self.suite_dir, match )
                if os.path.isfile(inc):
                    #print "Inlining", inc
                    h = open(inc, 'rb')
                    inc = h.readlines()
                    h.close()
                    # recursive inclusion
                    outf.extend( self.include_files( inc ))
                else:
                    raise SystemExit( "File not found: " + inc )
            else:
                # no match
                outf.append( line )
        return outf

    def continuation_lines( self, inf ):
        outf = []
        cline = ''
        for line in inf:
            # detect continuation line endings
            m = re.match( '(.*)\\\$', line )
            if m:
                # add line to cline instead of appending to outf.
                cline += m.groups()[0]
            else:
                outf.append( cline + line )
                # reset cline 
                cline = ''
        return outf


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
                    self._handle_error("Cannot compute the section depth at line %s.",
                                       NestingError, infile, cur_index)
                    continue
                
                if cur_depth < this_section.depth:
                    # the new section is dropping back to a previous level
                    try:
                        parent = self._match_depth(this_section,
                                                   cur_depth).parent
                    except SyntaxError:
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
                    self._handle_error("Section too nested at line %s.",
                                       NestingError, infile, cur_index)
                    
                sect_name = self._unquote(sect_name)
                if sect_name in parent:
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
                    'Invalid line at line "%s".',
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
                            self._handle_error(msg, UnreprError, infile,
                                cur_index)
                            continue
                    else:
                        # extract comment and lists
                        try:
                            (value, comment) = self._handle_value(value)
                        except SyntaxError:
                            self._handle_error(
                                'Parse error in value at line %s.',
                                ParseError, infile, cur_index)
                            continue
                #
                key = self._unquote(key)
                if key in this_section:
                    # CYLC CHANGE START: ALLOW DUPLICATE KEYWORDS TO OVERRIDE
                    # PREVIOUS VALUES IN 'environment'SECTIONS.
                    if sect_name == 'environment':
                        print 'WARNING: variable override (' + key + '), suite.rc line ' + str(cur_index)
                    else:
                        self._handle_error(
                                'Duplicate keyword name at line %s.',
                                DuplicateError, infile, cur_index)
                        continue
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


