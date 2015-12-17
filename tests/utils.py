import mock

from shub import config


def mock_conf(testcase, target=None, attr=None, conf=None):
    if not conf:
        conf = config.ShubConfig()
        conf.projects.update({
            'default': 1,
            'prod': 2,
            'vagrant': 'vagrant/3',
        })
        conf.endpoints.update({
            'vagrant': 'https://vagrant_ep/api/scrapyd/',
        })
        conf.apikeys.update({
            'default': 32 * '1',
            'vagrant': 32 * '2',
        })
        conf.version = 'version'
    if target:
        if attr:
            patcher = mock.patch.object(target, attr, return_value=conf,
                                        autospec=True)
        else:
            patcher = mock.patch(target, return_value=conf, autospec=True)
    else:
        patcher = mock.patch('shub.config.load_shub_config', return_value=conf,
                             autospec=True)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return conf
