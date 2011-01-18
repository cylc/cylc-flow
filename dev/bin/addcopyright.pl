#!/usr/bin/perl

$count = 0;
while (<>) {
    if ( $count == 1 ) {
        print <<eof

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

eof
    }
    $count += 1;
    print;
}

