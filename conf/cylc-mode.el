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

(setq cylc-font-lock-keywords
      '(("{%[[:alnum:], _=\\(\\)]*%}" . font-lock-constant-face) 
	("{{[[:alnum:] ]*}}" . font-lock-constant-face) 
        ("\\[\\[\\[[[:alnum:], _]+\\]\\]\\]" . font-lock-type-face)
        ("\\[\\[\\[[[:alnum:], _]+" . font-lock-type-face)
        ("\\]\\]\\]" . font-lock-type-face)
	("\\[\\[[[:alnum:], _]*\\]\\]" . font-lock-function-name-face)
	("\\[\\[[[:alnum:], _]*" . font-lock-function-name-face)
	("\\]\\]" . font-lock-function-name-face)
	("\\[[[:alnum:], ]+\\]" . font-lock-warning-face)
        ("^[[:alnum:] -_]*=" . font-lock-variable-name-face)
	))

;; define the mode
(define-derived-mode cylc-mode shell-script-mode
  "cylc mode"
  "Major mode for editing CYLC .cylc files"

  ;; code for syntax highlighting
  (setq font-lock-defaults '(cylc-font-lock-keywords))

)

(provide 'cylc-mode)

(add-hook 'cylc-mode-hook
  (lambda ()
    (font-lock-add-keywords nil
       '(("\\({%[[:alnum:], _=\\(\\)]*%}\\|{{[[:alnum:] ]*}}\\)" 0
	  font-lock-constant-face t)))))

