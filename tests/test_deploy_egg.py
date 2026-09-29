import os
import shutil
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

from click.testing import CliRunner

from shub import deploy_egg
from shub.exceptions import BadParameterException, NotFoundException


class FakeRequester:
    """Used to mock shub.utils#make_deploy_request"""
    def fake_request(self, *args):
        self.url = args[0]
        self.data = args[1]
        self.files = args[2]
        self.auth = args[3]


@mock.patch.dict(os.environ, {'SHUB_APIKEY': '1234'})
class TestDeployEgg(unittest.TestCase):

    def setUp(self):
        self.curdir = os.getcwd()
        self.fake_requester = FakeRequester()
        deploy_egg.utils.make_deploy_request = self.fake_requester.fake_request
        self.tmp_dir = tempfile.mkdtemp(prefix="shub-test-deploy-eggs")

    def tearDown(self):
        os.chdir(self.curdir)
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def test_parses_project_information_correctly(self):
        # this test's assertions are based on the values
        # defined on this folder's setup.py file
        shutil.rmtree(self.tmp_dir)
        shutil.copytree('tests/samples/deploy_egg_sample_project', self.tmp_dir)
        os.chdir(self.tmp_dir)

        data = self.call_main_and_check_request_data()
        self.assertEqual('1.2.0', data['version'])

    def test_can_clone_a_git_repo_and_deploy_the_egg(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = os.path.join(self.tmp_dir, 'deploy_egg_sample_repo.git')

        data = self.call_main_and_check_request_data(from_url=repo)

        self.assertTrue('master' in data['version'])

    @unittest.skip('flaky')
    def test_can_deploy_an_egg_from_pypi(self):
        basepath = os.path.abspath('tests/samples/')
        pkg = os.path.join(basepath, 'deploy_egg_sample_project.zip')
        self.call_main_and_check_request_data(from_pypi=pkg)

    def test_can_clone_checkout_and_deploy_the_egg(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = os.path.join(self.tmp_dir, 'deploy_egg_sample_repo.git')

        branch = 'dev'
        data = self.call_main_and_check_request_data(from_url=repo, git_branch=branch)
        self.assertTrue('dev' in data['version'])

    def test_fails_on_invalid_repo(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = os.path.join(self.tmp_dir, 'deploy_egg_sample_repo.git')
        shutil.rmtree(os.path.join(repo, '.git'))

        with self.assertRaises(BadParameterException):
            self.call_main_and_check_request_data(from_url=repo)

    def test_fails_on_invalid_branch(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = os.path.join(self.tmp_dir, 'deploy_egg_sample_repo.git')
        with self.assertRaises(BadParameterException):
            self.call_main_and_check_request_data(
                from_url=repo, git_branch='nonexisting')

    def _copy_sample_project_to(self, path):
        shutil.rmtree(path)
        shutil.copytree('tests/samples/deploy_egg_sample_project', path)

    def test_can_deploy_egg_from_directory(self):
        self._copy_sample_project_to(self.tmp_dir)
        with tempfile.TemporaryDirectory() as cwd:
            os.chdir(cwd)
            data = self.call_main_and_check_request_data(
                from_directory=self.tmp_dir)
        self.assertEqual('1.2.0', data['version'])

    def test_from_directory_resolves_target_from_cwd(self):
        self._copy_sample_project_to(self.tmp_dir)
        with tempfile.TemporaryDirectory() as cwd:
            with open(os.path.join(cwd, 'scrapinghub.yml'), 'w') as f:
                f.write('projects:\n  default: 12345\n  prod: 67890\n')
            os.chdir(cwd)
            missing_global = os.path.join(cwd, 'missing-global.yml')
            with mock.patch('shub.config.GLOBAL_SCRAPINGHUB_YML_PATH',
                            missing_global):
                deploy_egg.main('prod', from_directory=self.tmp_dir)
        self.assertEqual(67890, self.fake_requester.data['project'])
        self.assertEqual('test_project', self.fake_requester.data['name'])

    def test_from_directory_restores_cwd(self):
        self._copy_sample_project_to(self.tmp_dir)
        with tempfile.TemporaryDirectory() as cwd:
            os.chdir(cwd)
            expected = os.getcwd()
            deploy_egg.main(0, from_directory=self.tmp_dir)
            self.assertEqual(expected, os.getcwd())

    def test_from_directory_without_setup_py(self):
        with self.assertRaises(NotFoundException):
            deploy_egg.main(0, from_directory=self.tmp_dir)

    def test_from_directory_and_from_url_are_exclusive(self):
        with self.assertRaises(BadParameterException):
            deploy_egg.main(0, from_url='https://example.com/repo.git',
                            from_directory=self.tmp_dir)

    def test_from_directory_must_exist(self):
        missing = os.path.join(self.tmp_dir, 'does-not-exist')
        result = CliRunner().invoke(
            deploy_egg.cli, ['0', '--from-directory', missing])
        self.assertEqual(2, result.exit_code)
        self.assertIn('does not exist', result.output)

    def _unzip_git_repo_to(self, path):
        zipped_repo = os.path.abspath('tests/samples/deploy_egg_sample_repo.git.zip')
        ZipFile(zipped_repo).extractall(path)

    def call_main_and_check_request_data(self, project_id=0, from_url=None,
                                         git_branch=None, from_pypi=None,
                                         from_directory=None):
        # WHEN
        deploy_egg.main(project_id, from_url, git_branch, from_pypi,
                        from_directory)

        data = self.fake_requester.data
        files = self.fake_requester.files

        # THEN
        # the egg was successfully built, let's check the data
        # that is sent to the scrapy cloud
        self.assertTrue('test_project', files['egg'][0])
        self.assertEqual(project_id, data['project'])
        self.assertEqual('test_project', data['name'])

        return data
