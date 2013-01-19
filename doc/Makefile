#!/usr/bin/make -f

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

CYLC=$(dir $(abspath $(lastword $(MAKEFILE_LIST))))../bin/cylc

.PHONY: all commands clean tidy html html-multi html-single pdf index

# The main phony targets below depend initially on 'commands', which
# regenerates commands.tex only if the command usage help has changed.
# The real targets cannot have phony prerequisites as that would make
# them execute every time. Consequently: DO NOT USE THE REAL TARGETS
# DIRECTLY OR commands.tex WILL NOT BE REGENERATED WHEN IT SHOULD BE.
#   E.g. use 'make pdf' NOT 'make cug.pdf'.
# The index is regenerated for every real target; this is OK because 
# it is fast, and the index links to all the final documents found.

all: commands pdf html

html: commands html-multi html-single

html-multi: commands html/multi/cug-html.html

html-single: commands html/single/cug-html.html

pdf: commands pdf/cug-pdf.pdf

# just for standalone use: "make index"
index:
	./scripts/make-index.sh

commands:
	./scripts/make-commands.sh

html/multi/cug-html.html: commands.tex cug-html.tex cug.tex cug-html.cfg
	./scripts/scale-images.sh
	./scripts/make-html.sh multi
	./scripts/make-index.sh

html/single/cug-html.html: commands.tex cug-html.tex cug.tex cug-html.cfg
	./scripts/scale-images.sh
	./scripts/make-html.sh single
	./scripts/make-index.sh

pdf/cug-pdf.pdf: commands.tex cug-pdf.tex cug.tex
	./scripts/make-pdf.sh
	./scripts/make-index.sh

# delete all generated files:
clean:
	rm -rf pdf\
		html\
        command-usage\
        commands.tex\
        graphics/png-scaled \
        index.html \
        cylc-version.txt\

