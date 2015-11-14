
from PyInstaller.utils.hooks import collect_data_files

# Add the data files in the hubstorage package (aka hubstorage.VERSION).
datas = collect_data_files('hubstorage')
