/**
 * @fileoverview
 * Registers a language handler for cylc suite.rc files.
 */

PR['registerLangHandler'](
  PR['createSimpleLexer'](
    [
      [PR['PR_STRING'], /^"""[\s\S]+?"""/, null, '"""'],
    ],
    [
      [PR['PR_COMMENT'], /\{#[\s\S]+?#\}/ ],
      [PR['PR_LITERAL'], /^\s*\d+\s*?/ ],
      [PR['PR_DECLARATION'], /^\[+.+\]+/ ],
      [PR['PR_KEYWORD'], /^\s+[\w-\s]+=/ ],
      [PR['PR_STRING'], /\{\{[\s\S]+?\}\}/ ],
      [PR['PR_STRING'], /\{%[\s\S]+?%\}/ ],
      [PR['PR_COMMENT'], /^\s*#.+?\n/ ],
    ]
  ), ['cylc']);
