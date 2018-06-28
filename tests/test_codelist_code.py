import pytest

from ocdsdocumentationsupport.models import CodelistCode


def test_init():
    obj = fixture()

    assert obj.data == {'Code': 'tender', 'Title': 'Tender', 'Description': '…'}
    assert obj.extension_name == 'OCDS Core'


def test_eq():
    obj = fixture()

    assert obj == fixture()


def test_eq_dict():
    obj = fixture()

    assert obj == arguments()[0]


def test_getitem():
    obj = fixture()

    assert obj['Code'] == 'tender'

    with pytest.raises(KeyError) as excinfo:
        obj['nonexistent']

    assert str(excinfo.value) == "'nonexistent'"


def test_get():
    obj = fixture()

    assert obj.get('Code') == 'tender'

    assert obj.get('nonexistent', 'default') == 'default'


def test_setitem():
    obj = fixture()
    obj['Extension'] = 'OCDS Core'

    assert obj['Extension'] == 'OCDS Core'


def test_iter():
    obj = fixture()
    for i, item in enumerate(obj):
        pass

    assert i == 2


def test_len():
    obj = fixture()

    assert len(obj) == 3


def test_pop():
    obj = fixture()

    assert obj.pop('Code', 'default') == 'tender'

    assert obj.pop('Code', 'default') == 'default'

    with pytest.raises(KeyError) as excinfo:
        obj['Code']

    assert str(excinfo.value) == "'Code'"


def fixture():
    return CodelistCode(*arguments())


def arguments():
    return {'Code': 'tender', 'Title': 'Tender', 'Description': '…'}, 'OCDS Core'
