# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import secrets
import string
import time
from copy import deepcopy

# This is a standalone performance test of the algorithm used in gcylc to
# sort namespaces into "definition order", i.e. the order in which they are
# defined in the suite.rc file.

# Number of namespaces.
N = 10000

# N names of length 5-15 characters each (c.f. namespaces in "definition
# order").
names = []
for i in range(0, N):
    names.append(''.join(secrets.choice(string.ascii_letters)
                         for n in range(5 + secrets.randrange(10))))

# N lists with 2-7 names each (c.f. tree view paths of the inheritance
# hierarchy).
paths1 = []
for i in range(0, N):
    p = []
    for j in range(0, 2 + secrets.randrange(6)):
        z = secrets.randrange(0, N)
        p.append(names[z])
    paths1.append(p)

paths2 = deepcopy(paths1)

# Alphanumeric sort.
s = time.time()
paths1.sort()
t1 = time.time() - s

dict_names = dict(zip(names, range(0, len(names))))

# Definition order sort.
s = time.time()
paths2.sort(key=lambda x: map(dict_names.get, x))
t2 = time.time() - s

print("Alphanumeric sort:", t1, "sec")
print("Definition sort:", t2, "sec")
print(" => factor of", t2 / t1)
