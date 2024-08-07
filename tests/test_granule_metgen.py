from nsidc.granule_metgen import greeting


def test_greeting():
    assert greeting(None) == "Hello, None"
