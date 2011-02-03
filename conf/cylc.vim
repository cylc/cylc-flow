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

syn match cylcItem ' *\zs\(\w\| \|\-\)*\>\ze *='

syn match cylcInclude '%include *\(\w\|\-\|\/\|\.\)*'

syn match cylcComment excludenl '#.*'
syn region cylcString start=+"+ end=+"+ skip=+\\"+ 
syn region cylcString start=+'+ end=+'+ skip=+\\'+ 
syn region cylcString start=+"""+ end=+"""+ 
syn region cylcString start=+'''+ end=+'''+

hi def link cylcSection Function
hi def link cylcComment Comment
hi def link cylcString String
hi def link cylcItem Special
hi def link cylcInclude Statement


hi Normal ctermfg=DarkGrey guifg=#444444
hi Function ctermfg=DarkRed guifg=#0000aa term=bold cterm=bold gui=bold
hi Comment ctermfg=LightBlue guifg=#ff4422 term=bold cterm=bold gui=bold 
hi String ctermfg=DarkGreen guifg=#126412
hi Special term=Underline cterm=Underline gui=Underline ctermfg=DarkGrey guifg=#4444aa
hi Statement ctermbg=Yellow guibg=#bcff84 guifg=#222222
