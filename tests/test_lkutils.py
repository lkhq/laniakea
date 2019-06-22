
from laniakea.utils import compare_versions


def test_simple():
    assert compare_versions('1', '2') < 0
