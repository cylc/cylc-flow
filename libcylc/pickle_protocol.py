#! /usr/bin/env python

import pickle

invert = """(S'report'
p1
S'get_report'
p2
(S'm214089'
p3
tp4
(dp5
tp6
.
"""


value = ('report', 'get_report', ('m214089', ), {} )

protocol = 0

data = pickle.dumps(value,protocol)

# intermediate format
print type(data), len(data)

print "-"*50
if protocol == 2:
    print data.encode("hex")
else:
    print data
print "-"*50

print pickle.loads(data)

print pickle.loads(invert)


