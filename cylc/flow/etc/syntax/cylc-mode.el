;; ____________________________________________________________________________
;;
;; = cylc-mode.el =
;;    Emacs syntax highlighting mode for Cylc workflow definition (flow.cylc)
;;    files
;; ____________________________________________________________________________
;;
;; = Instructions =
;;    Place this file in $HOME/.emacs.d/lisp/ (create this directory if it
;;    doesn't exist) and add the following lines in your $HOME/.emacs file:
;;
;;         (add-to-list 'load-path "~/.emacs.d/lisp/")
;;         (require 'cylc-mode)
;;
;; ____________________________________________________________________________

(defvar cylc-mode-hook nil)

;; Extend region hook to ensure correct re-fontifying of the multi-line region
(defun cylc-font-lock-extend-region ()
  "Extend the search region to include an entire block of text."
  ;; Avoid compiler warnings about these global variables from font-lock.el.
  ;; See the documentation for variable `font-lock-extend-region-functions'.
  (eval-when-compile (defvar font-lock-beg) (defvar font-lock-end))
  (save-excursion
    (goto-char font-lock-beg)
    (let ((found (or (re-search-backward "\n\n" nil t) (point-min))))
      (goto-char font-lock-end)
      (when (re-search-forward "\n\n" nil t)
        (beginning-of-line)
        (setq font-lock-end (point)))
      (setq font-lock-beg found))))

;; Define the mode and the syntax highlighting for it
(define-derived-mode cylc-mode fundamental-mode
  "flow.cylc" "Major mode for editing Cylc workflow definition files"

  ;; Note: ordered according to reverse application precedence, where
  ;; specification order for faces changes resultant highlighting

  ;; Assignment and dependency characters, but only outside of Jinja2
  (font-lock-add-keywords nil '(("=+" . font-lock-preprocessor-face)))
  (font-lock-add-keywords nil '(("=>" . font-lock-keyword-face)))

  ;; Cylc setting keys/names
  (font-lock-add-keywords nil
    '(("^\\( *[a-zA-Z0-9\-]+ *\\)=+[^>]" 1 font-lock-variable-name-face t)))

  ;; Account for section headings (see below) with internal patterns, e.g. a
  ;; Jinja2 statement, inside by matching start and end heading groups. Note:
  ;; must be applied here to get correct 'pure' header & ICD highlighting.
  (font-lock-add-keywords nil
    '(("\\[\\( *[ a-zA-Z0-9\-\_,.]*\\)" . font-lock-warning-face)))
  (font-lock-add-keywords nil
    '(("\\( *[ a-zA-Z0-9\-\_,.]*\\)\\]" . font-lock-warning-face)))
  (font-lock-add-keywords nil
    '(("\\[\\[\\( *[ a-zA-Z0-9\-\_,.]*\\)" . font-lock-function-name-face)))
  (font-lock-add-keywords nil
    '(("\\( *[ a-zA-Z0-9\-\_,.]*\\)\\]\\]" . font-lock-function-name-face)))
  (font-lock-add-keywords nil
    '(("\\[\\[\\[\\( *[ a-zA-Z0-9\-\_,.]*\\)" . font-lock-type-face)))
  (font-lock-add-keywords nil
    '(("\\( *[ a-zA-Z0-9\-\_,.]*\\)\\]\\]\\]" . font-lock-type-face)))

  ;; Inter-cycle dependencies (distinguish from top-level section headings)
  (font-lock-add-keywords nil '(("\\[.*\\]" . font-lock-string-face)))

  ;; All 'pure' Cylc section (of any level e.g. sub-, sub-sub-) headings:
  ;; ... Top-level headings, enclosed in single square brackets
  (font-lock-add-keywords nil '(("^ *\\[.*\\]$" . font-lock-warning-face)))
  ;; ... Second-level (sub-) section headings, enclosed in double brackets
  (font-lock-add-keywords nil
    '(("^ *\\[\\[.*\\]\\]$" . font-lock-function-name-face)))
  ;; ... Third-level (sub-sub-) section headings, enclosed in triple brackets
  (font-lock-add-keywords nil
    '(("^ *\\[\\[\\[.*\\]\\]\\]$" . font-lock-type-face)))

  ;; All comments: standard ('# ... ') and Jinja2 ('{# ... #}')
  (font-lock-add-keywords nil
    '(("#.*$" . font-lock-comment-face)))  ;; in-line only, by precedence
  ;; Stop interference. No regex lookarounds in Emacs Lisp; ugly workaround
  (font-lock-add-keywords nil
    '(("^#\\(\\([^{].{2}\\|.[^#]\\).*\\|.{0,1}\\)$"
      . font-lock-comment-face)))
  (font-lock-add-keywords nil
    '(("{#\\(.\\|\n\\)*?#}" . font-lock-comment-face)))  ;; not in-line

  ;; All Jinja2 excl. comments: '{% ... %}' and '{{ ... }}' incl. multiline
  (font-lock-add-keywords nil
    '(("{%\\(.\\|\n\\)*?%}" . font-lock-constant-face)))
  (font-lock-add-keywords nil '(("{{.*?}}" . font-lock-constant-face)))

  ;; Highlight triple quotes for a multi-line setting value
  (font-lock-add-keywords nil '(("\"\"\"" . 'font-lock-builtin-face)))

  ;; Add the extend region hook to deal with the multiline matching above
  (add-hook 'font-lock-extend-region-functions 'cylc-font-lock-extend-region)

  ;; Make sure jit-lock scans larger multiline regions correctly
  (set (make-local-variable 'jit-lock-contextually) t)

  ;; Force any other fundamental mode inherit font-locking to be ignored, this
  ;; previously caused double-quotes to break the multiline highlighting
  (set (make-local-variable 'font-lock-keywords-only) t)

  ;; We need multiline mode
  (set (make-local-variable 'font-lock-multiline) t)

  ;; Run the mode hooks to allow a user to execute mode-specific actions
  (run-hooks 'cylc-mode-hook))

;;;###autoload
(add-to-list 'auto-mode-alist '("suite.*\\.rc\\'" . cylc-mode))
(add-to-list 'auto-mode-alist '("\\.cylc\\'" . cylc-mode))

(provide 'cylc-mode)
