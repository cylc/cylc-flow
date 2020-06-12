#!/usr/bin/env python3


def faker(name, debug=False):
    print("%s: failing" % name)
    return (False, {"name": name})
