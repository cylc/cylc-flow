#!/usr/bin/env python

# This subclasses ConfigParser in order to get it to use and OrderedDict
# data structure - so that order of cylc environment variable definition
# is preserved.

# This module is only necessary for Python 2.4:
#  * Python 2.6 has a dict_type ConfigParser init argument,
#  * Python 2.7 has a standard OrderedDict type.
# See also documentation in src/OrderedDict.py

from ConfigParser import SafeConfigParser
from OrderedDict import OrderedDict

class CylcSafeConfigParser( SafeConfigParser ):
    def __init__( self, defaults=None ):
        self._sections = OrderedDict()
        self._defaults = OrderedDict()
        if defaults:
            for key, value in defaults.items():
                self._defaults[ self.optionxform(key) ] = value

    def add_section(self, section):
        """Create a new section in the configuration.

        Raise DuplicateSectionError if a section by the specified name
        already exists.
        """
        if section in self._sections:
            raise DuplicateSectionError(section)
        self._sections[section] = OrderedDict()

    def items(self, section):
        try:
            d2 = self._sections[section]
        except KeyError:
            if section != DEFAULTSECT:
                raise NoSectionError(section)
            d2 = OrderedDict()
        d = self._defaults.copy()
        d.update(d2)
        if "__name__" in d:
            del d["__name__"]
        return d.items()
