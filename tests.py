import os
import pytest

import galleria


@pytest.fixture
def client():
    galleria.app.config['TESTING'] = True
    client = galleria.app.test_client()
    with galleria.app.app_context():
        yield client


def test_root(client):
    rv = client.get('/')
    print(rv.headers)
    assert rv.status_code == 302
    assert '/index' in rv.headers.get('Location')


def test_index(client):
    rv = client.get('/index')
    assert b'<form id="show-form"' in rv.data
