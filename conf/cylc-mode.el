;; Simple syntax highlighting for cylc suite definition files.
;; Author: Luis Kornblueh, 2012
;;
;; 1. copyt this file to $HOME/.emacs.d
;; 2. add in $HOME/.emacs the following lines:
;;
;;   (setq load-path (cons (expand-file-name "~/.emacs.d") load-path))
;;   (require 'cylc-mode)
;;   (setq auto-mode-alist (append auto-mode-alist 
;;			      (list '("\\.rc$" . cylc-mode))))
;;   (global-font-lock-mode t)
;;______________________________________________________________________________

(defconst cylc-mode-version "0.01")

(setq cylc-font-lock-keywords
      '(("\\[\\[\\[[[:alnum:], ]+\\]\\]\\]" . font-lock-constant-face)
	("\\[\\[[[:alnum:], _]*\\]\\]" . font-lock-warning-face)
	("\\[[[:alnum:], ]+\\]" . font-lock-builtin-face)
        ("\\<\\(title\\|description\\)\\>" . font-lock-type-face)
	("\\<\\(cold-start\\|start-up\\)\\>" . font-lock-function-name-face)
        ("\\<\\(graph\\|initial cycle time\\|final cycle time\\|cycling\\)\\>"
	 . font-lock-function-name-face)
	))

;; define the mode
(define-derived-mode cylc-mode shell-script-mode
  "cylc mode"
  "Major mode for editing CYLC .cylc files"

  ;; code for syntax highlighting
  (setq font-lock-defaults '(cylc-font-lock-keywords))

)

(provide 'cylc-mode)
