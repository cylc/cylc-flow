#!/usr/bin/env python3
"""Create Syntax keys from SPEC
"""

import re

from pathlib import Path

from cylc.flow.cfgspec.workflow import SPEC


LANG_FILE_PATH = Path(__file__).parent.parent.parent / 'cylc/flow/etc/syntax'
PRIVATE_NAMES = ['__MANY__', 'cylc.flow']


def get_keywords_from_workflow_cfg():
    """Extract a list of keywords from workflow SPEC.
    """
    keywords = []
    for item in SPEC.walk():
        keywords += [item[1].name]

    keywords = sorted(set(keywords) - set(PRIVATE_NAMES))
    return list(reversed(keywords))


def update_cylc_lang(keywords, file_, template):
    """Modify cylc.lang File.

    Creates a replacement keyword section for a language file and inserts
    it into the file.

    Args:
        keywords (list):
            A list of keywords.
        file_ (str):
            Name of file to modify.
        template (str):
            String template for each keyword line in the config file.
            Should contain {word}.
    """
    filepath = LANG_FILE_PATH / file_
    # Create a new keywords section.
    repl_text = '<!--TAG_FOR_AUTO_UPDATE-->\n'
    for word in keywords:
        repl_text += template.format(word=word)
    repl_text += '        <!--END_TAG_FOR_AUTO_UPDATE-->'

    # Replace the keywords section the language file.
    text = filepath.read_text()
    regex = (
        r"(.*)(<!--TAG_FOR_AUTO_UPDATE-->.*<!--END_TAG_FOR_AUTO_UPDATE-->)(.*)"
    )
    text = re.match(regex, text, re.DOTALL | re.MULTILINE)
    text = text.groups()[0] + repl_text + text.groups()[2]
    filepath.write_text(text)


def main():
    keywords = get_keywords_from_workflow_cfg()
    update_cylc_lang(
        keywords,
        'cylc.lang',
        '        <keyword>{word}</keyword>\n'
    )
    update_cylc_lang(
        keywords,
        'cylc.xml',
        "        <RegExpr attribute='Keyword' String=' {word} '/>\n"
    )


if __name__ == '__main__':
    main()
