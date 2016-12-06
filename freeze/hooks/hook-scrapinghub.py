
from __future__ import absolute_import
from PyInstaller.utils.hooks import collect_data_files

# Add the data files in the scrapinghub package (aka scrapinghub.VERSION).
datas = collect_data_files('scrapinghub')
