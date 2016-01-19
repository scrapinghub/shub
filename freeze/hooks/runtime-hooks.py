import os
import sys

os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(
    sys._MEIPASS, 'requests', 'cacert.pem')
