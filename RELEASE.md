Release procedure for shub
==========================

The GitHub Actions build is configured to release `shub` to PyPI whenever
a new tag (starting with `v`, e.g. `v2.13.0`) is committed.

The steps to do a release are:

1. Install [bump-my-version](https://pypi.org/project/bump-my-version/) and
   [uv](https://docs.astral.sh/uv/).

2. Make sure you're at the tip of master, and then run:

       bump-my-version bump VERSION_PART

   In place of `VERSION_PART`, use one of `patch`, `minor` or `major`, meaning
   the part of the version number to be updated.

   This will create a new commit and tag updating the version number and
   setting `FALLBACK_SCRAPY_STACK` to the latest Scrapy Cloud stack, which is
   fetched from GitHub. If it cannot be fetched, e.g. while offline, nothing
   is committed: discard the changes with `git checkout .` and try again.

3. Push the changes and the new tag to trigger the release:

       git push origin master --tags

4. Once the build finishes, run `pip install shub` in a temporary virtualenv
   and make sure it's installing the latest version.

5. Create a release for the new tag at:

       https://github.com/scrapinghub/shub/releases
