
from os import read
import pytest

from cylc.flow.parsec import fileparse
from cylc.flow.parsec.fileparse import read_and_proc
from cylc.flow.parsec.exceptions import TemplateVarLanguageClash


@pytest.mark.parametrize(
    'templating, hashbang',
    [
        ['empy', 'jinja2'],
        ['jinja2', 'empy']
    ]
)
def test_read_and_proc_raises_TemplateVarLanguageClash(
    monkeypatch, tmp_path, templating, hashbang
):
    """func fails when diffn't templating engines set in hashbang and plugin.
    """

    def fake_process_plugins(_):
        extra_vars = {
            'env': {},
            'template_variables': {'foo': 52},
            'templating_detected': templating
        }
        return extra_vars
    monkeypatch.setattr(fileparse, 'process_plugins', fake_process_plugins)

    file_ = tmp_path / 'flow.cylc'
    file_.write_text(
        f'#!{hashbang}\nfoo'
    )

    with pytest.raises(TemplateVarLanguageClash) as exc:
        read_and_proc(file_)

    assert exc.type == TemplateVarLanguageClash
