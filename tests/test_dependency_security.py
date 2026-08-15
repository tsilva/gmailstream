from importlib.metadata import version

import pytest
from pyasn1.codec.der.decoder import decode
from pyasn1.error import PyAsn1Error
from pyasn1.type.univ import Integer


def numeric_version(package: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version(package).split("."))


def test_security_dependency_floors():
    assert numeric_version("cryptography") >= (50, 0, 0)
    assert numeric_version("httplib2") >= (0, 32, 0)
    assert numeric_version("idna") >= (3, 15)
    assert numeric_version("pyasn1") >= (0, 6, 4)


def test_malicious_unbounded_asn1_tag_is_rejected():
    hostile_long_tag = b"\x1f" + (b"\xff" * 4096) + b"\x00"

    with pytest.raises(PyAsn1Error):
        decode(hostile_long_tag)


def test_valid_der_integer_still_decodes():
    decoded, remainder = decode(b"\x02\x01\x2a", asn1Spec=Integer())

    assert int(decoded) == 42
    assert remainder == b""
