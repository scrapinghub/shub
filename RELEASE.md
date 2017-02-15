Release procedure for shub
==========================

The Travis build is configured to release shub to PyPI whenever a new tag is
committed.

The steps to do a release are:

1. Install [bumpversion](https://pypi.python.org/pypi/bumpversion)

2. Make sure you're at the tip of master, and then run:

       bumpversion VERSION_PART
    
   In place of `VERSION_PART`, use one of `patch`, `minor` or `major`, meaning
   the part of the version number to be updated.

   This will create a new commit and tag updating the version number.

3. Push the changes and the new tag to trigger the release:

       git push origin master --tags

4. Once the build finishes, run `pip install shub` in a temporary virtualenv
   and make sure it's installing the latest version.

5. Update the release information at:

       https://github.com/scrapinghub/shub/releases

   Travis and AppVeyor will automatically create a release draft and attach the
   binaries they built to it. Sometimes their timing leads to them creating
   multiple release drafts, in which case we need to combine them such that we
   have one release that has all three (Linux, OSX, Windows) binaries.
