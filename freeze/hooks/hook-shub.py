from PyInstaller.utils.hooks import collect_submodules

# Add as hidden imports all submodules from shub. This is because shub
# modules are loaded when it's executed.
hiddenimports = collect_submodules('shub')
