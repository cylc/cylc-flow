#!/usr/bin/perl

# Add licensing preamble to source files. If the file is a script
# put it immediately after the '#!' interpreter line, otherwise 
# put it right at the top.

$count = 0;
while (<>) {
    if ( $count == 0 ) {
        if ( m/#!/ ) {
            $skip = 1;
        } else {
            $skip = 0;
        }
    }
    if ( $skip and $count == 1 or ! $skip and $count == 0 ) {
        print <<eof

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
eof
    }
    $count += 1;
    print;
}

