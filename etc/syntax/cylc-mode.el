;; Simple syntax highlighting for cylc suite definition files.
;;
;; 1. copy this file to $HOME/.emacs.d/lisp
;; 2. add in $HOME/.emacs the following lines:
;;
;;   (add-to-list 'load-path "~/.emacs.d/lisp/")
;;   (require 'cylc-mode)
;;   (setq auto-mode-alist (append auto-mode-alist 
;;			      (list '("\\.rc$" . cylc-mode))))
;;   (global-font-lock-mode t)
;;______________________________________________________________________________

(defconst cylc-mode-version "0.2")

;; No regular expression lookarounds in Emacs Lisp => some regexes ugly here
(setq cylc-font-lock-keywords
  '(
    ;; Ordered in terms precendence of application, where face specification
    ;; order changes resultant highlighting, so don't change ordering.

    ;; All comments: standard (# ...) and Jinja2 ('{# ... #}' incl. multiline)
    ("^#\\(\\([^{].{2}\\|.[^#]\\).*\\|.{0,1}\\)$" . font-lock-comment-face)
    ("^{#\\(\n?.?\\)*?[[:alnum:][[:punct:]]*#}$" . font-lock-comment-face)

    ;; Cylc setting keys/names
    ("^\\( *[[:alnum:]]+ *\\)=+" 1 font-lock-variable-name-face t)

    ;; Assignment and dependency characters, but only outside of Jinja2
    ("=>" . font-lock-keyword-face)  ;; as of 'special syntactic significance'
    ("=+" . font-lock-preprocessor-face)  ;; as running out of font-lock faces

    ;; All Jinja2 excl. comments: '{% ... %}' and '{{ ... }}' incl. multiline
    ("{%\\(\n?.?\\)*?[[:alnum:][[:punct:]]*%}" . font-lock-constant-face)
    ("{{[[:alnum:] [[:punct:]]+?}}" . font-lock-constant-face)

    ;; All Cylc section (of any level e.g. sub-, sub-sub-) specifications
    ("\\[\\[\\[[[:alnum:], _]+\\]\\]\\]" . font-lock-type-face)
    ("\\[\\[\\[[[:alnum:], _]+" . font-lock-type-face)
    ("\\]\\]\\]" . font-lock-type-face)
    ("\\[\\[[[:alnum:], _]+\\]\\]" . font-lock-type-face)
    ("\\[\\[[[:alnum:], _]+" . font-lock-type-face)
    ("\\]\\]" . font-lock-type-face)
    ("\\[[[:alnum:], ]+\\]" . font-lock-warning-face)
  )
)

;; Define the mode
(define-derived-mode cylc-mode fundamental-mode
  "cylc mode"
  "Major mode for editing CYLC .cylc files"

  ;; Double quotes treated as special in elisp, messing up mode, so turn off
  (setq font-lock-keywords-only t)

  ;; Code for syntax highlighting
  (setq font-lock-defaults '(cylc-font-lock-keywords))

)

(provide 'cylc-mode)

(add-hook 'cylc-mode-hook
  (lambda ()
    (font-lock-add-keywords nil
       '(("\\({%\\(\n?.?\\)+?[[:alnum:] _=\\(\\)[[:punct:]]%}\\|{{[[:alnum:] [[:punct:]]*?]*}}\\)" 0 font-lock-constant-face t)))))
