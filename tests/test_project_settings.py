import os

import pytest
from click.testing import CliRunner

from shub import utils
from shub.exceptions import BadConfigException
from shub.image.init import cli as image_init_cli


@pytest.fixture(autouse=True)
def isolated_env(tempdir, monkeypatch):
    """Run in an empty temp dir, ignoring the user's global scrapy.cfg files
    and any Scrapy environment variables set in the outer shell."""
    home = tempdir.mkdir('home')
    for var in ('HOME', 'USERPROFILE', 'XDG_CONFIG_HOME'):
        monkeypatch.setenv(var, str(home))
    for var in ('SCRAPY_SETTINGS_MODULE', 'SCRAPY_PROJECT'):
        monkeypatch.delenv(var, raising=False)
    return tempdir


def _write_scrapy_cfg(content):
    with open('scrapy.cfg', 'w') as f:
        f.write(content)


def _read_setup_py():
    with open('setup.py') as f:
        return f.read()


MULTI_PROJECT_CFG = "[settings]\ndefault = proj.settings\nother = other.settings\n"


def test_settings_module_from_scrapy_cfg_default():
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    assert utils._get_project_settings_module() == 'proj.settings'


def test_settings_module_env_var_takes_precedence(monkeypatch):
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'env.settings')
    monkeypatch.setenv('SCRAPY_PROJECT', 'other')
    assert utils._get_project_settings_module() == 'env.settings'


def test_settings_module_explicit_project_beats_env_var(monkeypatch):
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'env.settings')
    assert utils._get_project_settings_module('other') == 'other.settings'
    assert utils._get_project_settings_module('missing') is None


def test_settings_module_scrapy_project_selects_entry(monkeypatch):
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_PROJECT', 'other')
    assert utils._get_project_settings_module() == 'other.settings'


def test_settings_module_explicit_project_beats_scrapy_project(monkeypatch):
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_PROJECT', 'other')
    assert utils._get_project_settings_module('default') == 'proj.settings'


def test_settings_module_not_found():
    assert utils._get_project_settings_module() is None
    _write_scrapy_cfg("[deploy]\nproject = 123\n")
    assert utils._get_project_settings_module() is None
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    assert utils._get_project_settings_module('missing') is None


def test_inside_project_with_scrapy_project(monkeypatch):
    os.mkdir('sub')
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_PROJECT', 'other')
    os.chdir('sub')
    assert utils.inside_project()


def test_inside_project_nothing_configured():
    assert not utils.inside_project()


def test_inside_project_ignores_global_scrapy_cfg(isolated_env):
    # A [settings] section in a global scrapy.cfg must not turn every
    # directory into a project
    xdg_scrapy_cfg = isolated_env.join('home', 'scrapy.cfg')
    xdg_scrapy_cfg.write(MULTI_PROJECT_CFG)
    assert utils._get_project_settings_module() == 'proj.settings'
    assert not utils.inside_project()


def test_inside_project_unimportable_env_var(monkeypatch):
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'does_not_exist.settings')
    assert not utils.inside_project()


def test_create_default_setup_py_uses_scrapy_project(monkeypatch):
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_PROJECT', 'other')
    utils.create_default_setup_py()
    assert "'settings = other.settings'" in _read_setup_py()


def test_create_default_setup_py_env_var_without_settings_section(monkeypatch):
    _write_scrapy_cfg("[deploy]\nproject = 123\n")
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'env.settings')
    utils.create_default_setup_py()
    assert "'settings = env.settings'" in _read_setup_py()


def test_create_default_setup_py_env_var_without_scrapy_cfg(monkeypatch):
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'env.settings')
    utils.create_default_setup_py()
    assert "'settings = env.settings'" in _read_setup_py()


def test_create_default_setup_py_no_settings_module():
    _write_scrapy_cfg("[deploy]\nproject = 123\n")
    with pytest.raises(BadConfigException) as excinfo:
        utils.create_default_setup_py()
    assert 'SCRAPY_SETTINGS_MODULE' in excinfo.value.format_message()
    assert not os.path.exists('setup.py')


def _read_dockerfile():
    with open('Dockerfile') as f:
        return f.read()


def test_image_init_project_option_uses_that_project():
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    result = CliRunner().invoke(image_init_cli, ['--project', 'other'])
    assert result.exit_code == 0, result.output
    assert 'ENV SCRAPY_SETTINGS_MODULE other.settings' in _read_dockerfile()
    assert "'settings = other.settings'" in _read_setup_py()


def test_image_init_scrapy_project_env_var(monkeypatch):
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_PROJECT', 'other')
    result = CliRunner().invoke(image_init_cli, [])
    assert result.exit_code == 0, result.output
    assert 'ENV SCRAPY_SETTINGS_MODULE other.settings' in _read_dockerfile()


def test_image_init_settings_module_env_var(monkeypatch):
    _write_scrapy_cfg("[deploy]\nproject = 123\n")
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'env.settings')
    result = CliRunner().invoke(image_init_cli, [])
    assert result.exit_code == 0, result.output
    assert 'ENV SCRAPY_SETTINGS_MODULE env.settings' in _read_dockerfile()


def test_image_init_project_option_beats_env_var(monkeypatch):
    _write_scrapy_cfg(MULTI_PROJECT_CFG)
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'env.settings')
    result = CliRunner().invoke(image_init_cli, ['--project', 'other'])
    assert result.exit_code == 0, result.output
    assert 'ENV SCRAPY_SETTINGS_MODULE other.settings' in _read_dockerfile()
    assert "'settings = other.settings'" in _read_setup_py()


def test_image_init_no_settings_module():
    _write_scrapy_cfg("[deploy]\nproject = 123\n")
    result = CliRunner().invoke(image_init_cli, [])
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code == BadConfigException.exit_code
    assert 'SCRAPY_SETTINGS_MODULE' in result.output
    assert not os.path.exists('Dockerfile')


def _assert_image_init_refused(result):
    assert result.exit_code == BadConfigException.exit_code, result.output
    assert not os.path.exists('Dockerfile')
    assert not os.path.exists('setup.py')


def test_image_init_ignores_global_scrapy_cfg(isolated_env):
    # A [settings] section in a global scrapy.cfg must not make image init
    # write a Dockerfile and setup.py into an arbitrary directory
    isolated_env.join('home', 'scrapy.cfg').write(MULTI_PROJECT_CFG)
    _assert_image_init_refused(CliRunner().invoke(image_init_cli, []))


def test_image_init_unimportable_env_var_without_scrapy_cfg(monkeypatch):
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'does_not_exist.settings')
    _assert_image_init_refused(CliRunner().invoke(image_init_cli, []))


def test_image_init_importable_env_var_without_scrapy_cfg(isolated_env, monkeypatch):
    isolated_env.join('envproj', '__init__.py').write('', ensure=True)
    isolated_env.join('envproj', 'settings.py').write('')
    monkeypatch.syspath_prepend(str(isolated_env))
    monkeypatch.setenv('SCRAPY_SETTINGS_MODULE', 'envproj.settings')
    result = CliRunner().invoke(image_init_cli, [])
    assert result.exit_code == 0, result.output
    assert 'ENV SCRAPY_SETTINGS_MODULE envproj.settings' in _read_dockerfile()
    assert "'settings = envproj.settings'" in _read_setup_py()
