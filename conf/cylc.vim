" Simple syntax highlighting for cylc suite definition files.
" Author: Hilary Oliver, 2011

" Put this file in $HOME/.vim/syntax/ directory.

" And put the following in .vimrc file, for file type recognition:

"augroup filetype
"  au! BufRead,BufnewFile *.rc   set filetype=cylc
"augroup END


syn keyword cylcKeyword foo

syn match cylcSection '\[.*\]'
syn match cylcSection '\[\[.*\]\]'
syn match cylcSection '\[\[\[.*\]\]\]'

syn region myFold start='\_^ *\[\[\[\(\w\| \)' end='\ze\_^ *\[\{1,3}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\[\(\w\| \)' end='\ze\_^ *\[\{1,2}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\(\w\| \)' end='\_^ *\ze\[\(\w\| \)' transparent fold
set foldmethod=syntax

syn match cylcInlineMarker '\_^!\{1,}'
syn match cylcItem ' *\zs\(\w\| \|\-\)*\>\ze *='

syn match cylcInclude '%include *\(\w\|\-\|\/\|\.\)*'
syn match cylcInline '.*\(START INLINED\|END INLINED\).*'

syn match cylcComment excludenl '#.*'
syn region cylcString start=+"+ end=+"+ skip=+\\"+ 
syn region cylcString start=+'+ end=+'+ skip=+\\'+ 
syn region cylcString start=+"""+ end=+"""+ 
syn region cylcString start=+'''+ end=+'''+

hi def link cylcInlineMarker Statement
hi def link cylcSection Function
hi def link cylcComment Comment
hi def link cylcString String
hi def link cylcItem Special
hi def link cylcInline Statement
hi def link cylcInclude Statement


hi Normal ctermfg=DarkGrey guifg=#444444
hi Function ctermfg=DarkRed guifg=#aa00aa term=bold cterm=bold gui=bold
hi Comment ctermfg=LightBlue guifg=#ff4422 term=bold cterm=bold gui=bold 
hi String ctermfg=DarkGreen guifg=#126412
hi Special term=Underline cterm=Underline gui=Underline ctermfg=DarkGrey guifg=#4444aa
hi Statement ctermbg=Yellow guibg=#bcff84 guifg=#222222
