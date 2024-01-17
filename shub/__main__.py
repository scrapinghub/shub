import os
import sys

import shub.tool


prog_name = os.path.basename(sys.argv and sys.argv[0] or __file__)
if prog_name == '__main__.py':
    # shub invoked via python -m shub
    prog_name = __package__
shub.tool.cli(prog_name=prog_name)
