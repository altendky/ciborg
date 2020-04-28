import ciborg


def test_configuration_defaults_to_version(raw_configuration):
    expected = 'ciborg=={}'.format(ciborg.__version__)

    assert raw_configuration.ciborg_requirement == expected
