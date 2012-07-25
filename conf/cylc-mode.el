;; Simple syntax highlighting for cylc suite definition files.
;; Author: Luis Kornblueh, 2012
;;
;; 1. copy this file to $HOME/.emacs.d
;; 2. add in $HOME/.emacs the following lines:
;;
;;   (setq load-path (cons (expand-file-name "~/.emacs.d") load-path))
;;   (require 'cylc-mode)
;;   (setq auto-mode-alist (append auto-mode-alist 
;;			      (list '("\\.rc$" . cylc-mode))))
;;   (global-font-lock-mode t)
;;______________________________________________________________________________

(defconst cylc-mode-version "0.1")

;; (custom-set-faces
;;  '(font-lock-constant-face      ((t (:foreground "#00e7eb"))))
;;  '(font-lock-warning-face       ((t (:foreground "#00abad"))))
;;  '(font-lock-function-name-face ((t (:foreground "#0054ad"))))
;;  '(font-lock-type-face          ((t (:foreground "#5a00ad"))))
;;  '(font-lock-variable-name-face ((t (:foreground "#abad00"))))
;;  '(font-lock-comment-face       ((t (:foreground "#54ad00"))))
;;  '(font-lock-doc-face           ((t (:foreground "#00ad5a"))))
;;  )

(setq cylc-font-lock-keywords
      '(("{%[[:alnum:] _=\\(\\),]*%}" . font-lock-constant-face) 
	("{{[[:alnum:] ]*}}" . font-lock-constant-face) 
        ("\\[\\[\\[[[:alnum:], _]+\\]\\]\\]" . font-lock-type-face)
        ("\\[\\[\\[[[:alnum:], _]+" . font-lock-type-face)
        ("\\]\\]\\]" . font-lock-type-face)
	("\\[\\[[[:alnum:], _]*\\]\\]" . font-lock-function-name-face)
	("\\[\\[[[:alnum:], _]*" . font-lock-function-name-face)
	("\\]\\]" . font-lock-function-name-face)
	("\\[[[:alnum:], ]+\\]" . font-lock-warning-face)
        ("\\<\\(title\\|description\\)\\>" . font-lock-function-name-face)
        ("^[[:alnum:] -_]*=" . font-lock-variable-name-face)
	))

;; Define the mode
(define-derived-mode cylc-mode sh-mode
  "cylc mode"
  "Major mode for editing CYLC .cylc files"

  ;; code for syntax highlighting
  (set (make-local-variable 'font-lock-defaults) '(cylc-font-lock-keywords nil t))
  ;; code for indenting
 ;; (set (make-local-variable 'indent-line-function 'cylc-indent-line)))
)

(provide 'cylc-mode)

(add-hook 'cylc-mode-hook
  (lambda ()
    (font-lock-add-keywords nil
       '(("\\({%[[:alnum:], _='\"\\(\\)]*%}\\|{{[[:alnum:] _\(\)\|\+]*}}\\)" 0
	  font-lock-constant-face t)))))


