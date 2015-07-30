#!/bin/bash

# Usage: $0 PREFIX N
#   Create, register, and start, N suites registered as ${PREFIX}_$n
# The suites are started with --hold to minimize system load.
# See also stop-n-suites.sh.

set -eu

PREFIX=$1
N=$2

TOP_DIR=$TMPDIR/$$

mkdir -p $TOP_DIR/${PREFIX}_1
cat >> $TOP_DIR/${PREFIX}_1/suite.rc << __END__
[cylc]
    cycle point format = %Y-%m
[scheduling]
    initial cycle point = 2015-08
    [[dependencies]]
        [[[P1M]]]
            graph = "foo => bar & baz & qux"
__END__

cylc reg ${PREFIX}_1 $TOP_DIR/${PREFIX}_1
cylc val ${PREFIX}_1

for I in $(seq 2 $N); do
    cylc cp ${PREFIX}_1 ${PREFIX}_$I $TOP_DIR
done

for I in $(seq 1 $N); do
    cylc run --hold ${PREFIX}_$I
done

cylc scan
