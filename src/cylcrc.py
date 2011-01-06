#!/usr/bin/env python

import re, os, sys
from validate import Validator
from configobj import ConfigObj, get_extra_values


home = os.environ[ 'HOME' ]
cylcrc_file = os.path.join( home, '.cylcrc' )
spec_file = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'preferences.spec')

class preferences( ConfigObj ):
    def __init__( self, file=None, spec=None ):
        if file:
            self.file = file
        else:
            self.file = cylcrc_file

        if spec:
            self.spec = spec
        else:
            self.spec = spec_file

        # load config
        ConfigObj.__init__( self, self.file, configspec=self.spec )

        # validate and convert to correct types
        val = Validator()
        test = self.validate( val )
        if test != True:
            # TO DO: elucidate which items failed
            # (easy - see ConfigObj and Validate documentation: flatten_errors?)
            print test
            print >> sys.stderr, "Cylc Preferences Validation Failed"
            sys.exit(1)
        
        # are there any keywords or sections not present in the spec?
        found_extra = False
        for sections, name in get_extra_values(self):
            # this code gets the extra values themselves
            the_section = self
            for section in sections:
                the_section = self[section]
            # the_value may be a section or a value
            the_value = the_section[name]
            section_or_value = 'value'
            if isinstance(the_value, dict):
                # Sections are subclasses of dict
                section_or_value = 'section'

            section_string = ', '.join(sections) or "top level"
            print 'Extra entry in section: %s. Entry %r is a %s' % (section_string, name, section_or_value)
            found_extra = True

        if found_extra:
            print >> sys.stderr, "Illegal .cylcrc preferences entry found"
            sys.exit(1)

        # make logging and state directories relative to $HOME
        # unless specified as absolute paths
        logdir = self['logging directory']
        if not re.match( '^/', logdir ):
           self['logging directory'] = os.path.join( home, logdir )
        statedir = self['state dump directory']
        if not re.match( '^/', statedir ):
           self['state dump directory'] = os.path.join( home, statedir )

