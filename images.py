import os
import time
import re
from datetime import datetime
from PIL import Image, IptcImagePlugin

from flask import current_app

import db
import config

IPTC_KEYWORDS = (2, 25)
IPTC_DATE_CREATED = (2, 55)
IPTC_TIME_CREATED = (2, 60)

iptc_tags = {
    (1, 90): 'CodedCharacterSet',
    (2, 0): 'RecordVersion',
    (2, 5): 'ObjectName',  # title
    IPTC_KEYWORDS: 'Keywords',
    IPTC_DATE_CREATED: 'DateCreated',
    IPTC_TIME_CREATED: 'TimeCreated',
    (2, 62): 'DigitizationDate',
    (2, 63): 'DigitizationTime',
    (2, 80): 'Byline',  # author
    (2, 120): 'Caption',
}


# noinspection SqlResolve
def sync_bundle(path, bundle):
    current_app.logger.debug("Path: %s Bundle: %s" % (path, bundle))
    # List files in directory
    files = [f for f in os.listdir(path) if f.lower().endswith('.jpg')]
    files.sort()
    items = {f: 2 for f in files}
    # Look what is already present in database
    images = db.fetch("SELECT id, name FROM " + db.tbl_image + " WHERE bundle = %s", [bundle])
    ids = {}
    for image in images:
        if items[image['name']] == 3:
            # Remove duplicates
            remove_image(image['id'])
            continue
        items[image['name']] += 1
        ids[image['name']] = image['id']
    # Analyze what was found
    for name in sorted(items):
        # Image is in the directory but not in database
        if items[name] == 2:
            add_image(bundle, name)
        # Image is in the database but not in the directory
        elif items[name] == 1:
            remove_image(ids[name])
        # Image is in sync, currently do nothing
        else:
            update_metadata(ids[name], bundle, name)
            # pass


# noinspection SqlResolve
def add_image(bundle, name):
    # TODO: Use gmtime instead?
    localtime = time.localtime()
    now = time.strftime("%Y-%m-%d %H:%M:%S", localtime)
    image_id = db.execute("INSERT INTO " + db.tbl_image + "(bundle, name, ctime) VALUES(%s, %s, %s) RETURNING id",
                          [bundle, name, now])
    db.commit()
    update_metadata(image_id, bundle, name)


def update_metadata(image_id, bundle, name):
    image = Image.open(''.join([config.ROOT_DIR, bundle, '/', name]))

    iptc_info = IptcImagePlugin.getiptcinfo(image) or {}
    exif_info = image._getexif() or {}

    timestamp_str = ''

    for tag, value in iptc_info.items():
        if tag == IPTC_KEYWORDS:
            pass
        if tag == IPTC_DATE_CREATED:
            current_app.logger.debug('DateCreated: %s' % value)
            timestamp_str = value.decode('utf-8') + timestamp_str
        if tag == IPTC_TIME_CREATED:
            current_app.logger.debug('TimeCreated: %s' % value)
            timestamp_str = timestamp_str + value.decode('utf-8')

    timestamp = None
    if len(timestamp_str) == 14:
        timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
    elif exif_info[36867]:
        timestamp = datetime.strptime(exif_info[36867], '%Y:%m:%d %H:%M:%S')

    db.execute("UPDATE " + db.tbl_image + " SET width = %s, height = %s, stime = %s WHERE id = %s",
               [image.width, image.height, timestamp, image_id])
    db.commit()


# noinspection SqlResolve
def remove_image(image_id):
    db.execute("DELETE FROM " + db.tbl_image_log + " WHERE image = %s", [image_id])
    db.execute("DELETE FROM " + db.tbl_image_rating + " WHERE image = %s", [image_id])
    db.execute("DELETE FROM " + db.tbl_image_referrer + " WHERE image = %s", [image_id])
    db.execute("DELETE FROM " + db.tbl_image_label + " WHERE image = %s", [image_id])
    db.execute("DELETE FROM " + db.tbl_image + " WHERE id = %s", [image_id])
    db.commit()


def make_thumbnail(path, size='m', force=False):
    # Construct path to thumbnail and return it if file exists
    thumbnail_path = re.sub(r'/([^/]+)$', r'/thumbs/t%s-\1' % size, path)
    if os.path.isfile(thumbnail_path) and os.path.getsize(thumbnail_path) > 0 and not force:
        return thumbnail_path
    # Create directory if it not exists
    thumbnail_dir = os.path.dirname(thumbnail_path)
    if not os.path.isdir(thumbnail_dir):
        os.makedirs(thumbnail_dir, 0o750)
    # Rescale and save image
    with Image.open(path) as image:
        ox = image.width
        oy = image.height
        nx = int(config.THUMBNAIL_WIDTH[size])
        ny = int(oy * nx / ox)
        image.thumbnail((nx, ny))
        if os.path.isfile(thumbnail_path):
            os.remove(thumbnail_path)
        image.save(thumbnail_path)
    # Return path to thumbnail
    return thumbnail_path
