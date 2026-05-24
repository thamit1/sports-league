import sys
import os

VENV_DIR   = os.path.expanduser('~/sports-league/.venv')
PYTHON_312 = os.path.join(VENV_DIR, 'bin', 'python3.12')
APP_DIR    = os.path.expanduser('~/sports-league/backend')

# This MUST happen before any Python 3.6+ syntax
# because Passenger boots with an old Python first
if sys.executable != PYTHON_312:
    os.execv(PYTHON_312, [PYTHON_312] + sys.argv)

sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.join(VENV_DIR, 'lib', 'python3.12', 'site-packages'))

# version check - using old-style string formatting (safe for old Python)
with open('/tmp/py_check.txt', 'w') as f:
    f.write("Executable: %s\nVersion: %s\n" % (sys.executable, sys.version))

from a2wsgi import ASGIMiddleware
from app.main import app

application = ASGIMiddleware(app)
