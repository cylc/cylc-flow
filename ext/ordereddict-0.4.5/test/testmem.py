
import sys
import string
from _ordereddict import ordereddict

def do_empty():
    d = ordereddict()

def do_small():
    d = ordereddict()
    for i in range(5):
        d[i]  = i

def do_one():
    d = ordereddict()
    index = 0
    for ch1 in string.lowercase:
        for ch2 in string.lowercase:
            for ch3 in string.lowercase:
                d[ch1 + ch2] = index
                index += 1

for i in range(1000000):
    if i % 100 == 0:
        print '\r %8d' % ( i ),
        sys.stdout.flush()
    do_one()
