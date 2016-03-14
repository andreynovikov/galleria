EXPORT_MAX_WIDTH = 400
EXPORT_MAX_HEIGHT = 300

SCREEN_MAX_WIDTH = 1200
SCREEN_MAX_HEIGHT = 1024
SCREEN_DELTA = 1.1

THUMBNAIL_WIDTH = {
    's': 80,
    'm': 200,
    'l': 400
}

ROOT_DIR = '### SPECIFY PATH TO IMAGES ROOT DIRECTORY WITHOUT TRAILING SLASH ###'
DB_CONNECTION_DSN = 'postgresql:///galleria'  # set correct DSN
DB_TABLE_PREFIX = ''

try:
    from local_config import *
except ImportError:
    # no local config found
    pass
