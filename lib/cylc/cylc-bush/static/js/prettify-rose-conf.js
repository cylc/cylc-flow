/**
 * @fileoverview
 * Registers a language handler for Rose configuration files.
 */

PR['registerLangHandler'](
  PR['createSimpleLexer'](
    [],
    [
      [PR['PR_COMMENT'], /^\[!!?[^!].*\]/ ],
      [PR['PR_COMMENT'], /^!!?[^!].*/ ],
      [PR['PR_DECLARATION'],  /^\[[^!].+\]/ ],
      [PR['PR_STRING'], /=.*/ ],
      [PR['PR_STRING'], /\n\s+[\w-].*/ ],
      [PR['PR_COMMENT'], /^#.*/ ],
    ]
  ), ['rose_conf']);
