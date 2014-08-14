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

" see :help syntax

" syncing from start of file is best, but may be slow for large files:
syn sync fromstart

" contained items are only recognized inside containing items
syn match lineCon "\\$"
syn match badLineCon "\\ \+$"
syn match trailingWS " \+\(\n\)\@="

syn region jinja2 start='{%' end='%}'
syn region jinja2variable start='{{' end='}}'
syn region jinja2comment start='{#' end='#}'

syn region cylcSectionA start='\[' end='\]' contains=trailingWS,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable
syn region cylcSectionB start='\[\[' end='\]\]' contains=trailingWS,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable
syn region cylcSectionC start='\[\[\[' end='\]\]\]' contains=trailingWS,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable

set foldmethod=syntax
syn region myFold start='\_^ *\[\[\[\(\w\| \)' end='\ze\_^ *\[\{1,3}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\[\(\w\| \)' end='\ze\_^ *\[\{1,2}\(\w\| \)' transparent fold
syn region myFold start='\_^ *\[\(\w\| \)' end='\_^ *\ze\[\(\w\| \)' transparent fold

syn match cylcInlineMarker '\_^!\{1,}'
syn match cylcItemKey ' *\zs\(\w\| \|\-\)*\> *='
syn match trigger /=>/ contained
syn match output /:[a-zA-Z0-9-]*\>/ contained
syn match suicide /\!\w\+/ contained
syn match offset /\[.\{-}\]/ contained

syn match cylcInclude '%include *\(\w\|\-\|\/\|\.\)*'
syn match cylcInline '.*\(START INLINED\|END INLINED\).*'

syn match cylcToDo /[Tt][Oo][Dd][Oo].*$/
syn match cylcComment /#.*/ contains=trailingWS,cylcToDo,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable
syn match cylcCommentInString /#.*/ contained contains=trailingWS,cylcToDo,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable

syn region String start=+'+ skip=+\\'+ end=+'+ contains=trailingWS,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable
syn region String start=+"+ skip=+\\"+ end=+"+ contains=trailingWS,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable
syn region String start=+=\@<= *"""+ end=+"""+ contains=trailingWS,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable,cylcCommentInString,trigger,output,suicide,offset
syn region String start=+=\@<= *'''+ end=+'''+ contains=trailingWS,lineCon,badLineCon,jinja2,jinja2comment,jinja2variable,cylcCommentInString,trigger,output,suicide,offset

hi def link jinja2InString jinja2
hi def link jinja2commentInString jinja2comment
hi def link jinja2variableInString jinja2variable
hi def link cylcInlineMarker cylcInlining
hi def link cylcInline cylcInlining
hi def link cylcInclude cylcInlining

hi Normal ctermfg=DarkGrey guifg=#666666 gui=None
hi String ctermfg=DarkGrey guifg=#666666 gui=None

hi trailingWS ctermbg=Grey guibg=#aaa
hi badLineCon ctermbg=Red guibg=red guifg=#fff
hi lineCon ctermfg=Green guifg=DarkBlue guibg=SkyBlue

hi cylcSectionC ctermfg=Black guifg=#600 term=bold cterm=bold gui=bold
hi cylcSectionB ctermfg=Black guifg=#600 term=bold cterm=bold gui=bold
hi cylcSectionA ctermfg=Black guifg=#600 term=bold cterm=bold gui=bold

hi jinja2         ctermfg=Blue ctermbg=yellow guifg=slategray guibg=#d8ff6f gui=None
hi jinja2comment  ctermfg=Red ctermbg=yellow guifg=white guibg=DeepPink gui=None 
hi jinja2variable ctermfg=Magenta ctermbg=yellow guifg=slategray guibg=#aaffd8 gui=None

hi cylcItemKey ctermfg=DarkBlue guifg=#28f cterm=bold gui=bold
hi cylcCommentInString ctermfg=red guifg=#f42 gui=italic
hi cylcComment ctermfg=red guifg=deeppink gui=italic
hi cylcInlining ctermbg=LightGrey ctermfg=DarkBlue guibg=#aff guifg=#00a
hi cylcToDo guibg=DeepPink
hi trigger guifg=#00cc00 gui=bold
hi output guifg=#aaaa3d
hi suicide guifg=#cc3dcc
hi offset guifg=#3d4ccc
