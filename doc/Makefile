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

.PHONY: all index clean html html-multi html-single pdf

DEPS := $(shell ./scripts/get-deps.sh)

all: index

index: $(DEPS)
	./scripts/make-index.sh

html: html-multi html-single

html-multi: html/multi/cug-html.html

html-single: html/single/cug-html.html

pdf: pdf/cug-pdf.pdf


cylc.txt: ../bin/cylc
	$< --help > $@

cats = $(shell ../bin/cylc categories) 
catx = $(cats:%=categories/%.txt)

cmds = $(shell ../bin/cylc commands)
cmdx = $(cmds:%=commands/%.txt)

$(cmdx): commands/%.txt: ../bin/cylc-%
	if test ! -d commands; then mkdir -p commands/; fi
	$(subst cylc-,cylc ,$<) --help > $@

$(catx): categories/%.txt: ../bin/cylc
	if test ! -d categories; then mkdir -p categories/; fi
	cylc $(subst .txt,,$(subst categories/,,$@)) --help > $@

commands.tex: $(cmdx) $(catx) cylc.txt
	./scripts/make-commands.sh

html/multi/cug-html.html: commands.tex cug-html.tex cug.tex cug-html.cfg
	./scripts/make-html.sh multi

html/single/cug-html.html: commands.tex cug-html.tex cug.tex cug-html.cfg
	./scripts/make-html.sh single

pdf/cug-pdf.pdf: commands.tex cug-pdf.tex cug.tex
	./scripts/make-pdf.sh

# delete all generated files:
clean:
	rm -r pdf \
	html \
	cylc.txt \
	commands \
	categories \
	commands.tex \
	index.html \
	cylc-version.txt

