"""
    MoinMoin - OpenID relying party tests

    @license: GNU GPL, see COPYING for details.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip('openid')

from MoinMoin.auth import CancelLogin
from MoinMoin.auth.openidrp import OpenIDAuth


def test_associate_continuation_without_openid_session():
    request = SimpleNamespace(
        session={},
        getText=lambda text, **kwargs: text,
    )

    result = OpenIDAuth()._handle_associate_continuation(request)

    assert isinstance(result, CancelLogin)
    assert result.message == 'No OpenID found in session.'
