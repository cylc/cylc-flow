#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
#------------------------------------------------------------------------------
# Test various uses of the cylc list command
. "$(dirname "$0")/test_header"
#------------------------------------------------------------------------------
set_test_number 10
#------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-val"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-basic
cylc list "${WORKFLOW_NAME}" > list.out
cmp_ok list.out << __DONE__
cujo
fido
manny
__DONE__
#------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-opt-a
cylc ls -a "${WORKFLOW_NAME}" > list-a.out
cmp_ok list-a.out << __DONE__
cujo
fido
manny
not-used
__DONE__
#------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-opt-n
cylc list -n "${WORKFLOW_NAME}" > list-n.out
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
TEST_NAME=${TEST_NAME_BASE}-opt-nw
cylc ls -nw "${WORKFLOW_NAME}" > list-nw.out
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
TEST_NAME=${TEST_NAME_BASE}-opt-nm
cylc list -nm "${WORKFLOW_NAME}" > list-nm.out
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
cat > res.out << __DONE__
20140808T0000Z/cujo
20140808T0000Z/fido
20140808T0000Z/manny
20140809T0000Z/cujo
20140809T0000Z/fido
20140809T0000Z/manny
20140810T0000Z/cujo
20140810T0000Z/fido
20140810T0000Z/manny
20140811T0000Z/cujo
20140811T0000Z/fido
20140811T0000Z/manny
20140812T0000Z/cujo
20140812T0000Z/fido
20140812T0000Z/manny
__DONE__

TEST_NAME=${TEST_NAME_BASE}-opt-p1
cylc ls -p 20140808T0000Z,20140812T0000Z "${WORKFLOW_NAME}" > list-p1.out
cmp_ok list-p1.out res.out

TEST_NAME=${TEST_NAME_BASE}-opt-p2
# default from initial point
cylc ls -p ,20140812T0000Z "${WORKFLOW_NAME}" > list-p2.out
cmp_ok list-p2.out res.out

cat > res2.out << __DONE__
20140808T0000Z/cujo
20140808T0000Z/fido
20140808T0000Z/manny
20140809T0000Z/cujo
20140809T0000Z/fido
20140809T0000Z/manny
20140810T0000Z/cujo
20140810T0000Z/fido
20140810T0000Z/manny
__DONE__


TEST_NAME=${TEST_NAME_BASE}-opt-p3
cylc ls -p 20140808T0000Z, "${WORKFLOW_NAME}" > list-p3.out
# default 3 cycle points
cmp_ok list-p3.out res2.out

TEST_NAME=${TEST_NAME_BASE}-opt-p4
cylc ls -p , "${WORKFLOW_NAME}" > list-p4.out
# default 3 cycle points from initial
cmp_ok list-p4.out res2.out
#------------------------------------------------------------------------------
purge
