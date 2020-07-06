import pytest

from cylc.flow.parsec.config import ConfigNode as Conf


@pytest.fixture(scope='module')
def basic_config():
    """A basic config with a file, section and setting."""
    with Conf('file.rc') as file_:
        with Conf('section') as section:
            setting = Conf('setting')
        return (file_, section, setting)


def test_config_node(basic_config):
    """It should associate parents & children in a tree."""
    file_, section, setting = basic_config
    assert file_.name == 'file.rc'
    assert file_._parent is None
    assert file_._children == {'section': section}

    assert section.name == 'section'
    assert section._parent == file_
    assert section._children == {'setting': setting}

    assert setting.name == 'setting'
    assert setting._parent == section
    assert setting._children is None


def test_config_str(basic_config):
    """A node should str as a relative path from its parent node.."""
    file_, section, setting = basic_config
    assert str(file_) == 'file.rc'
    assert str(section) == '[section]'
    assert str(setting) == 'setting'


def test_config_repr(basic_config):
    """A node should repr as a full path."""
    file_, section, setting = basic_config
    assert repr(file_) == 'file.rc'
    assert repr(section) == 'file.rc[section]'
    assert repr(setting) == 'file.rc[section]setting'


@pytest.fixture(scope='module')
def many_setting():
    """A config containing a user-definable setting."""
    with Conf('file.rc') as file_:
        Conf('<setting>')  # __MANY__
    return file_


def test_many_setting(many_setting):
    """It should recognise this is a user-definable setting."""
    setting = list(many_setting)[0]
    assert setting.name == '__MANY__'
    assert setting.display_name == '<setting>'
    assert str(setting) == '<setting>'
    assert repr(setting) == 'file.rc|<setting>'


@pytest.fixture(scope='module')
def many_section():
    """A config containing a user-definable section."""
    with Conf('file.rc') as file_:
        with Conf('<section>'):
            Conf('setting')
    return file_


def test_many_section(many_section):
    """It should recognise this is a user-definable section."""
    section = list(many_section)[0]
    assert section.name == '__MANY__'
    assert section.display_name == '<section>'
    assert str(section) == '[<section>]'
    assert repr(section) == 'file.rc[<section>]'
    setting = list(section)[0]
    assert str(setting) == 'setting'
    assert repr(setting) == 'file.rc[<section>]setting'


@pytest.fixture(scope='module')
def meta_conf():
    """A config with an inherited section."""
    with Conf('Foo') as spec:
        with Conf('<X>') as template:
            Conf('a', default='a')
            Conf('b', default='b')
        with Conf('y', meta=template) as copy:
            Conf('a', default='c')
    return spec, template, copy


def test_meta(meta_conf):
    """It should inherit sections using the meta kwarg."""
    spec, template, copy = meta_conf
    assert template.meta is None
    assert copy.meta == template
    # make sure the template is unaffected
    assert template['a'].default == 'a'
    assert template['b'].default == 'b'
    # make sure the copy is affected
    assert copy['a'].default == 'c'
    assert copy['b'].default == 'b'
    # make sure inherited configurations are marked accordingly
    assert copy['a'].meta is None  # not inherited
    assert copy['b'].meta is True  # inherited
