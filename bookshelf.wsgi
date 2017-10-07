import sys
import os

# Change working directory so relative paths (and template lookup) work again
os.chdir(os.path.dirname(__file__))
sys.path.append('./')

from main import COVER_PIC_DIR
try:
    if not os.path.exists(COVER_PIC_DIR):
        os.makedirs(COVER_PIC_DIR)
except Exception as e:
    print(e)

from main import app as application