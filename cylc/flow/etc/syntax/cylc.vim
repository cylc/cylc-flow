" Syntax highlighting for Cylc files.
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
"|  au! BufRead,BufnewFile *suite*.rc   set filetype=cylc
"|  au! BufRead,BufnewFile *.cylc   set filetype=cylc
"|augroup END
"
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

syn region jinja2Block start='{%' end='%}'
syn region jinja2Print start='{{' end='}}'
syn region jinja2Comment start='{#' end='#}'

syn region empy start='@\[' end=']'
syn region empy start='@{' end='}'
syn region empy start='@(' end=')'

syn region cylcSection start='\[' end='\]' contains=trailingWS,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy
syn region cylcSection start='\[\[' end='\]\]' contains=trailingWS,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy
syn region cylcSection start='\[\[\[' end='\]\]\]' contains=trailingWS,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy

syn match cylcItem ' *\zs\(\w\|+\|\/\| \|\-\)*\> *=\@='
syn match cylcEquals '='

syn match trigger /=>/ contained
syn match xtrigger /@[a-zA-Z0-9_-]*/ contained
syn match parameter /<[^>]*>/ contained
syn match output /:[a-zA-Z0-9_-]*\>/ contained
syn match suicide /\!\w\+/ contained
syn match offset /\[.\{-}\]/ contained
syn match optional /?/ contained

"file inclusion:
syn match cylcInclude '%include *\(\w\|"\| \|\-\|\/\|\.\)*'
"inlined file markers:
syn match cylcInclude '\_^!\{1,}'
syn match cylcInclude '.*\(START INLINED\|END INLINED\).*'

syn match cylcToDo /[Tt][Oo][Dd][Oo]/
syn match cylcToDo /[Ff][Ii][Xx][Mm][Ee]/

syn match empyVariable /@[a-zA-Z0-9]\+/
syn match empyComment /@#.*/ contains=trailingWS,cylcToDo,lineCon,badLineCon
syn match cylcComment /#.*/ contains=trailingWS,cylcToDo,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy

syn region cylcString start=+'+ skip=+\\'+ end=+'+ contains=trailingWS,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy,cylcToDo
syn region cylcString start=+"+ skip=+\\"+ end=+"+ contains=trailingWS,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy,cylcToDo
syn region cylcString start=+=\@<= *"""+ end=+"""+ contains=trailingWS,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy,empyComment,cylcComment,optional,trigger,output,suicide,offset,cylcToDo,xtrigger,parameter
syn region cylcString start=+=\@<= *'''+ end=+'''+ contains=trailingWS,lineCon,badLineCon,jinja2Block,jinja2Print,jinja2Comment,empy,empyComment,cylcComment,optional,trigger,output,suicide,offset,cylcToDo,xtrigger,parameter

"de-emphasize strings as quoting is irrelevant in cylc
hi def link cylcString Normal

hi def link cylcSection Statement
hi def link cylcItem Type
hi def link cylcComment Comment

hi def link lineCon Constant
hi def link badLineCon Error
hi def link trailingWS Underlined

hi def link cylcToDo Todo
hi def link cylcInclude Include
hi def link jinja2Block PreProc
hi def link jinja2Print PreProc
hi def link jinja2Comment Comment
hi def link empy PreProc
hi def link empyComment CursorColumn
hi def link empyVariable PreProc
hi def link cylcEquals LineNr
hi def link output Identifier
hi def link suicide Special
hi def link offset Special
hi def link trigger Constant
hi def link optional Type

hi def link xtrigger Function
hi def link parameter Function
