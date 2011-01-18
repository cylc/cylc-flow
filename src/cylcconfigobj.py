
from configobj import ConfigObj, ConfigObjError
import os, re

class CylcConfigObj( ConfigObj ):

    # OVERRIDE _load() to deal with:
    # (i) continuation lines
    # (ii) include files

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
