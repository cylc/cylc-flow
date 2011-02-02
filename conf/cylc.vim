" Simple syntax highlighting for cylc suite definition files.
" Put this file in $HOME/.vim/syntax/.

" Author: Hilary Oliver, 2011

syn keyword cylcKeyword foo

syn match cylcSection '\[.*\]'
syn match cylcSection '\[\[.*\]\]'
syn match cylcSection '\[\[\[.*\]\]\]'

syn match cylcItem '\(\w\| \|\-\)* *='

syn match cylcComment excludenl '#.*'
syn region cylcString start=+"+ end=+"+ skip=+\\"+ 
syn region cylcString start=+'+ end=+'+ skip=+\\'+ 
syn region cylcString start=+"""+ end=+"""+ 
syn region cylcString start=+'''+ end=+'''+

hi def link cylcSection Function
hi def link cylcComment Comment
hi def link cylcString String
hi def link cylcItem Special
