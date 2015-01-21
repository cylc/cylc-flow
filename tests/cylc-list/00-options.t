#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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
#------------------------------------------------------------------------------
# Test various uses of the cylc list command
. $(dirname $0)/test_header
#------------------------------------------------------------------------------
set_test_number 7
#------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_ok $TEST_NAME cylc validate $SUITE_NAME
#------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-basic
cylc list $SUITE_NAME > list.out
cmp_ok list.out << __DONE__
cujo
fido
manny
__DONE__
#------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-opt-a
cylc list -a $SUITE_NAME > list-a.out
cmp_ok list-a.out << __DONE__
cujo
fido
manny
not-used
__DONE__
#------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-opt-n
cylc list -n $SUITE_NAME > list-n.out
cmp_ok list-n.out << __DONE__
DOG
FICTIONAL
MAMMAL
POODLE
cujo
fido
manny
not-used
root
__DONE__
#------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-opt-nw
cylc list -nw $SUITE_NAME > list-nw.out
cmp_ok list-nw.out << __DONE__
DOG        a canid that is known as man's best friend
FICTIONAL  something made-up
MAMMAL     a clade of endothermic amniotes
POODLE     a ridiculous-looking dog owned by idiots
cujo       a fearsome man-eating poodle
fido       a large black and white spotted dog
manny      a large hairy mammoth
not-used   an unused namespace
root       
__DONE__
#------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-opt-nm
cylc list -nm $SUITE_NAME > list-nm.out
cmp_ok list-nm.out << __DONE__
DOG        DOG MAMMAL root
FICTIONAL  FICTIONAL root
MAMMAL     MAMMAL root
POODLE     POODLE DOG MAMMAL root
cujo       cujo POODLE DOG MAMMAL FICTIONAL root
fido       fido DOG MAMMAL root
manny      manny MAMMAL FICTIONAL root
not-used   not-used root
root       root
__DONE__
#------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-opt-p
cylc list -p 20140808T00,20140812T00 $SUITE_NAME > list-p.out
cmp_ok list-p.out << __DONE__
cujo.20140808T0000Z
cujo.20140809T0000Z
cujo.20140810T0000Z
cujo.20140811T0000Z
cujo.20140812T0000Z
fido.20140808T0000Z
fido.20140809T0000Z
fido.20140810T0000Z
fido.20140811T0000Z
fido.20140812T0000Z
manny.20140808T0000Z
manny.20140809T0000Z
manny.20140810T0000Z
manny.20140811T0000Z
manny.20140812T0000Z
__DONE__
#------------------------------------------------------------------------------
purge_suite $SUITE_NAME

