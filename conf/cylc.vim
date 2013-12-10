" Simple syntax highlighting for cylc suite definition files.
" Author: Hilary Oliver, 2011
"______________________________________________________________________
" 1/ Put this file in $HOME/.vim/syntax/ directory.

" 2/ Put the following in $HOME/.vimrc for file type recognition:

"augroup filetype
"  au! BufRead,BufnewFile *suite.rc   set filetype=cylc
"augroup END

" (the wildcard in '*suite.rc' handles temporary files generated
"  by the 'cylc view' command, e.g. /tmp/foo.bar.QYrZ0q.suite.rc)

" 3/ If you want to open files with syntax folds initially open, then
"    also add the following line to your $HOME/.vimrc file:

" set foldlevelstart=99
"----------------------------------------------------------------------

" syncing from start of file is best, but may be slow for large files:
syn sync fromstart

syn match jinja2 '{%.\{-}%}'
syn match jinja2variable '{{.\{-}}}'
"syn match jinja2comment '{#.\{-}#}'
syn region jinja2comment start='{#' end='#}'

syn match cylcSectionA '\[.*\]'
syn match cylcSectionB '\[\[.*\]\]'
syn match cylcSectionC '\[\[\[.*\]\]\]'

syn region myFold start='\_^ *\[\[\[\(\w\| \)' end='\ze\_^ *\[\{1,3}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\[\(\w\| \)' end='\ze\_^ *\[\{1,2}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\(\w\| \)' end='\_^ *\ze\[\(\w\| \)' transparent fold
set foldmethod=syntax

syn match cylcInlineMarker '\_^!\{1,}'
syn match cylcItem ' *\zs\(\w\| \|\-\)*\>\ze *='

syn match cylcInclude '%include *\(\w\|\-\|\/\|\.\)*'

syntax keyword ToDo TODO ToDo contained
syn match cylcComment excludenl '#.*' contains=ToDo
syn match cylcCommentInString '#.*[^"']' contained contains=ToDo

syn match jinja2InString '{%.\{-}[^"']%}' contained
syn match jinja2variableInString '{{.\{-}[^"']}}' contained
syn match jinja2commentInString '{#.\{-}[^"']#}' contained

syn region cylcString start=+"+ end=+"+ skip=+\\"+ contains=jinja2InString,jinja2commentInString,jinja2variableInString,cylcCommentInString keepend
syn region cylcString start=+'+ end=+'+ skip=+\\'+ contains=jinja2InString,jinja2commentInString,jinja2variableInString,cylcCommentInString keepend
syn region cylcString start=+"""+ end=+"""+ contains=jinja2InString,jinja2commentInString,jinja2variableInString,cylcCommentInString keepend
syn region cylcString start=+'''+ end=+'''+ contains=jinja2InString,jinja2commentInString,jinja2variableInString,cylcCommentInString keepend

" TO DO: replace the following with cylc-specific groups as for cylcSectionA,B,C:
hi def link cylcCommentInString Comment
hi def link jinja2InString jinja2
hi def link jinja2commentInString jinja2comment
hi def link jinja2variableInString jinja2variable
hi def link cylcComment Comment
hi def link cylcInlineMarker Statement
hi def link cylcString String
hi def link cylcItem Special
hi def link cylcInclude Statement

hi Normal ctermfg=DarkGrey guifg=#444444

hi cylcSectionC ctermfg=DarkRed guifg=#550044 term=bold cterm=bold gui=bold
hi cylcSectionB ctermfg=DarkRed guifg=#9900aa term=bold cterm=bold gui=bold
hi cylcSectionA ctermfg=DarkRed guifg=#ff00ee term=bold cterm=bold gui=bold

hi jinja2         ctermfg=DarkGrey guifg=#666 term=bold cterm=bold gui=bold
hi jinja2comment  ctermfg=DarkGrey guifg=#776 term=bold cterm=bold gui=bold 
hi jinja2variable ctermfg=DarkGrey guifg=#677 term=bold cterm=bold gui=bold

hi Comment ctermfg=LightBlue guifg=#ff4422 term=bold cterm=bold gui=bold 
hi cylcCommentInString ctermfg=LightBlue guifg=#ff8844 term=bold cterm=bold gui=bold 
hi String ctermfg=DarkGreen guifg=#18a329
hi Special term=Underline cterm=Underline gui=Underline ctermfg=Blue guifg=#0082d3
hi Statement ctermbg=Yellow ctermfg=Blue guibg=#aff guifg=#00a
