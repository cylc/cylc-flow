#!/usr/bin/env python3

#import os, sys
#sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib', 'python'))

import local_lookup

def qualify(arg):
    return local_lookup.lookup(arg)
