import os
from click.testing import CliRunner
from unittest import TestCase
from shub import exceptions as shub_exceptions

from shub_image.init import cli
from shub_image.init import _format_system_deps
from shub_image.init import _format_system_env
from shub_image.init import _format_requirements
from shub_image.init import _wrap

from .utils import FakeProjectDirectory
from .utils import add_fake_requirements
from .utils import add_scrapy_fake_config


BASE_DOCKERFILE = """\
FROM python:2.7
RUN apt-get update -qq && \\
    apt-get install -qy htop iputils-ping lsof ltrace strace telnet vim && \\
    rm -rf /var/lib/apt/lists/*
ENV TERM xterm
ENV PYTHONPATH $PYTHONPATH:/app
ENV SCRAPY_SETTINGS_MODULE test.settings
RUN mkdir -p /app
WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app\
"""


class TestInitCli(TestCase):

    def test_cli_default_settings(self):
        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, [], input='no\n')
            assert result.exit_code == 0
            assert BASE_DOCKERFILE in result.output
            assert not os.path.exists(os.path.join(tmpdir, 'Dockerfile'))

    def test_cli_list_recommended_reqs(self):
        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, ["--list-recommended-reqs"])
            assert result.exit_code == 0
            assert "Recommended Python deps list:" in result.output

    def test_cli_store_dockerfile(self):
        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, [], input='yes\n')
            assert result.exit_code == 0
            assert BASE_DOCKERFILE in result.output
            assert os.path.exists(os.path.join(tmpdir, 'Dockerfile'))

    def test_wrap(self):
        short_cmd = "run short command wrapping another one short"
        assert _wrap(short_cmd) == short_cmd
        assert _wrap(short_cmd + ' ' + short_cmd) == (
            short_cmd + ' ' + ' '.join(short_cmd.split()[:3]) +
            " \\\n    "  + ' '.join(short_cmd.split()[3:]))

    def test_format_system_deps(self):
        # no deps at all
        assert _format_system_deps('-', None) == None
        # base deps only
        assert _format_system_deps('a,b,cd', None) == (
            "RUN apt-get update -qq && \\\n"
            "    apt-get install -qy a b cd && \\\n"
            "    rm -rf /var/lib/apt/lists/*")
        # base & additional deps only
        assert _format_system_deps('a,b,cd', 'ef,hk,b') == (
            "RUN apt-get update -qq && \\\n"
            "    apt-get install -qy a b cd ef hk && \\\n"
            "    rm -rf /var/lib/apt/lists/*")
        # additional deps only
        assert _format_system_deps('-', 'ef,hk,b') == (
            "RUN apt-get update -qq && \\\n"
            "    apt-get install -qy b ef hk && \\\n"
            "    rm -rf /var/lib/apt/lists/*")

    def test_format_system_env(self):
        assert _format_system_env(None) == 'ENV TERM xterm'
        assert _format_system_env('test.settings') == (
            "ENV TERM xterm\n"
            "ENV PYTHONPATH $PYTHONPATH:/app\n"
            "ENV SCRAPY_SETTINGS_MODULE test.settings")

    def test_format_requirements(self):
        with FakeProjectDirectory() as tmpdir:
            add_fake_requirements(tmpdir)
            basereqs = os.path.join(tmpdir, 'requirements.txt')
            if os.path.exists(basereqs):
                os.remove(basereqs)
            # use given requirements
            assert _format_requirements(
                os.getcwd(), 'fake-requirements.txt') == (
                    "COPY ./fake-requirements.txt /app/requirements.txt\n"
                    "RUN pip install --no-cache-dir -r requirements.txt")
            assert not os.path.exists(basereqs)
            # using base requirements
            assert _format_requirements(
                os.getcwd(), 'requirements.txt') == (
                    "COPY ./requirements.txt /app/requirements.txt\n"
                    "RUN pip install --no-cache-dir -r requirements.txt")
            assert os.path.exists(basereqs)
            os.remove(basereqs)
