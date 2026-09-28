import os
import sys
from pathlib import Path

os.environ["REQUESTS_CA_BUNDLE"] = str(Path(sys._MEIPASS, "requests", "cacert.pem"))
