" Syntax highlighting for cylc suite.rc files.
" Author: Hilary Oliver, 2011-2014
" see :help syntax
"______________________________________________________________________
"
"INSTRUCTIONS FOR USE
"
" 1) Put this file in $HOME/.vim/syntax/ directory.
"
" 2) Put the following in $HOME/.vimrc for file type recognition
"    (without the leading "| characters):
"
"|augroup filetype
"|  au! BufRead,BufnewFile *suite.rc   set filetype=cylc
"|augroup END
"
" (the wildcard in '*suite.rc' handles temporary files generated
"  by the 'cylc view' command, e.g. /tmp/foo.bar.QYrZ0q.suite.rc)

" 3) If you want to open files with syntax folds initially open, then
"    also add the following line to your $HOME/.vimrc file:
"
"|if has("folding") | set foldlevelstart=99 | endif
"
" 4) Cylc syntax is linked to standard vim highlighting groups below (e.g.
" comments: 'hi def link cylcComment Comment'). These can be customized in
"  your .vimrc file for consistent highlighting across file types, e.g.:
"
"|hi Statement guifg=#22a8e3 gui=bold 
"|hi Normal guifg=#9096a4
"|hi Comment guifg=#ff6900
"|hi Type guifg=#28d45b gui=bold"
"
"______________________________________________________________________

" syncing from start of file is best, but may be slow for large files:
syn sync fromstart

set foldmethod=syntax
syn region myFold start='\_^ *\[\[\[\(\w\| \)' end='\ze\_^ *\[\{1,3}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\[\(\w\| \)' end='\ze\_^ *\[\{1,2}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\(\w\| \)' end='\_^ *\ze\[\(\w\| \)' transparent fold

" note contained items are only recognized inside containing items
syn match lineCon "\\$"
syn match badLineCon "\\ \+$"
syn match trailingWS " \+\(\n\)\@="

syn region jinja2 start='{%' end='%}'
syn region jinja2 start='{{' end='}}'
syn region jinja2 start='{#' end='#}'

syn region cylcSection start='\[' end='\]' contains=trailingWS,lineCon,badLineCon,jinja2
syn region cylcSection start='\[\[' end='\]\]' contains=trailingWS,lineCon,badLineCon,jinja2
syn region cylcSection start='\[\[\[' end='\]\]\]' contains=trailingWS,lineCon,badLineCon,jinja2

syn match cylcItem ' *\zs\(\w\| \|\-\)*\> *=\@='
syn match cylcEquals '='

syn match trigger /=>/ contained
syn match output /:[a-zA-Z0-9-]*\>/ contained
syn match suicide /\!\w\+/ contained
syn match offset /\[.\{-}\]/ contained

"file inclusion:
syn match cylcInclude '%include *\(\w\|\-\|\/\|\.\)*'
"inlined file markers:
syn match cylcInclude '\_^!\{1,}'
syn match cylcInclude '.*\(START INLINED\|END INLINED\).*'

syn match cylcToDo /[Tt][Oo][Dd][Oo]/

syn match cylcComment /#.*/ contains=trailingWS,cylcToDo,lineCon,badLineCon,jinja2

syn region cylcString start=+'+ skip=+\\'+ end=+'+ contains=trailingWS,lineCon,badLineCon,jinja2,cylcToDo
syn region cylcString start=+"+ skip=+\\"+ end=+"+ contains=trailingWS,lineCon,badLineCon,jinja2,cylcToDo
syn region cylcString start=+=\@<= *"""+ end=+"""+ contains=trailingWS,lineCon,badLineCon,jinja2,cylcComment,trigger,output,suicide,offset,cylcToDo
syn region cylcString start=+=\@<= *'''+ end=+'''+ contains=trailingWS,lineCon,badLineCon,jinja2,cylcComment,trigger,output,suicide,offset,cylcToDo

"de-emphasize strings as quoting is irrelevant in cylc
hi def link cylcString Normal

hi def link cylcSection Statement
hi def link cylcItem Type
hi def link cylcComment Comment

hi def link lineCon Constant
hi def link badLineCon Error
hi def link trailingWS Underlined

hi def link cylcToDo Todo
hi def link cylcInclude MatchParen
hi def link jinja2 CursorColumn
hi def link cylcEquals LineNr
hi def link output Special
hi def link suicide Special
hi def link offset Special
hi def link trigger Constant 
