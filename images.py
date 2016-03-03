import os
import time
import re
from PIL import Image, ExifTags, IptcImagePlugin

from flask import current_app

import db
import config


iptc_tags = {
    (2, 0): 'RecordVersion',
    (2, 5): 'ObjectName',  # title
    (2, 25): 'Keywords',
    (2, 55): 'DateCreated',
    (2, 60): 'TimeCreated',
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
            pass


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
    for tag, value in iptc_info.items():
        decoded = iptc_tags.get(tag, str(tag))
        if decoded == 'Keywords':
            pass
    db.execute("UPDATE " + db.tbl_image + " SET width = %s, height = %s WHERE id = %s",
               [image.width, image.height, image_id])
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
