import os
import time
import re
from datetime import datetime
from PIL import Image, ExifTags, IptcImagePlugin

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
def sync_bundle(path, bundle, should_update_metadata=False):
    current_app.logger.debug("Path: %s Bundle: %s" % (path, bundle))
    # List files in directory
    files = [f for f in os.listdir(path) if f.lower().endswith('.jpg')]
    files.sort()
    items = {f: 2 for f in files}
    # Look what is already present in database
    images = db.fetch("SELECT id, name FROM " + db.tbl_image + " WHERE bundle=%s", [bundle])
    ids = {}
    for image in images:
        if items[image['name']] == 3:
            # Remove duplicates
            im = GalleriaImage.fromid(image['id'])
            im.remove(keep_file=True)
            continue
        items[image['name']] += 1
        ids[image['name']] = image['id']
    # Analyze what was found
    for name in sorted(items):
        image = GalleriaImage.fromid(ids[name])
        # Image is in the directory but not in database
        if items[name] == 2:
            add_image(bundle, name)
        # Image is in the database but not in the directory
        elif items[name] == 1:
            image.remove()
        # Image is in sync, update metadata if requested
        elif should_update_metadata:
            update_metadata(ids[name], bundle, name)


# noinspection SqlResolve
def add_image(bundle, name):
    # TODO: Use gmtime instead?
    localtime = time.localtime()
    now = time.strftime("%Y-%m-%d %H:%M:%S", localtime)
    image_id = db.execute("INSERT INTO " + db.tbl_image + "(bundle, name, ctime) VALUES(%s,%s,%s) RETURNING id",
                          [bundle, name, now])
    db.commit()
    update_metadata(image_id, bundle, name)


def update_metadata(image_id, bundle, name):
    image = Image.open(''.join([config.ROOT_DIR, bundle, '/', name]))

    iptc_info = IptcImagePlugin.getiptcinfo(image) or {}
    exif_info = image._getexif() or {}

    timestamp = None

    if IPTC_DATE_CREATED in iptc_info and IPTC_TIME_CREATED in iptc_info:
        timestamp_str = iptc_info[IPTC_DATE_CREATED].decode('utf-8') + iptc_info[IPTC_TIME_CREATED].decode('utf-8')
        timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
    elif 36867 in exif_info:
        timestamp_str = exif_info[36867]
        timestamp = datetime.strptime(timestamp_str, '%Y:%m:%d %H:%M:%S')

    if IPTC_KEYWORDS in iptc_info:
        pass

    db.execute("UPDATE " + db.tbl_image + " SET width = %s, height = %s, stime = %s WHERE id = %s",
               [image.width, image.height, timestamp, image_id])
    db.commit()


# noinspection PyUnresolvedReferences
class GalleriaImage(object):
    def __init__(self, dictionary):
        for k, v in dictionary.items():
            setattr(self, k, v)

    @classmethod
    def fromid(cls, image_id):
        assert type(image_id) is int, "id is not an integer: %r" % image_id
        _object = cls({'id': image_id})
        return _object

    @classmethod
    def frompath(cls, image_path, open=False):
        assert type(image_path) is str, "path is not a string: %r" % image_path
        _object = cls({'path': image_path})
        if open:
            pass
        return _object

    # noinspection SqlResolve
    def remove(self, keep_file=False):
        db.execute("DELETE FROM " + db.tbl_image_log + " WHERE image=%s", [self.id])
        db.execute("DELETE FROM " + db.tbl_image_rating + " WHERE image=%s", [self.id])
        db.execute("DELETE FROM " + db.tbl_image_referrer + " WHERE image=%s", [self.id])
        db.execute("DELETE FROM " + db.tbl_image_label + " WHERE image=%s", [self.id])
        db.execute("DELETE FROM " + db.tbl_image + " WHERE id=%s", [self.id])
        db.commit()
        # todo: add file deletion

    # noinspection SqlResolve
    def fetch_data(self):
        # do not fetch twice
        if hasattr(self, 'ctime'):
            return
        assert hasattr(self, 'id'), "id must be set before fetching data"
        data = db.fetch("SELECT * FROM " + db.tbl_image + " WHERE id=%s", [self.id], True)
        for k, v in data.items():
            setattr(self, k, v)

    def get_data(self, path_prefix=''):
        data = {}
        for a in self.__dict__:
            attr = getattr(self, a)
            # skip python internals, file handlers, unset properties and class methods
            if not a.startswith('__') and not a in ['image'] and attr is not None and not callable(attr):
                data[a] = attr
                if a in ['stime', 'ctime', 'mtime']:
                    data[a] = data[a].isoformat()
        data['path'] = ''.join([path_prefix, self.bundle, '/', self.name])
        return data

    def ensure_path(self):
        if hasattr(self, 'path'):
            return
        if not hasattr(self, 'name'):
            self.fetch_data()
        self.path = ''.join([config.ROOT_DIR, self.bundle, '/', self.name])

    def open(self):
        if hasattr(self, 'image'):
            return
        self.ensure_path()
        self.image = Image.open(self.path)

    def expand(self):
        self.fetch_data()
        # Get rating
        # cursor.execute("SELECT AVG(rating) AS average FROM " + tbl_image_rating + " WHERE image = %s GROUP BY image", [imageId])
        # rating = cursor.fetchone()
        # if rating != None:
        #    image['rating'] = rating

        # Get labels
        # cursor.execute("SELECT id, name FROM " + tbl_label + " INNER JOIN " + tbl_image_label + " ON (label = id AND image = %s)", [imageId])
        # labels = cursor.fetchall()
        # if labels != None:
        #    image['labels'] = labels

        # get meta data
        self.open()
        exif = {}
        iptc = {}
        exif_info = self.image._getexif() or {}
        for tag, value in exif_info.items():
            decoded = ExifTags.TAGS.get(tag, str(tag))
            exif[decoded] = value
        iptc_info = IptcImagePlugin.getiptcinfo(self.image) or {}
        for tag, value in iptc_info.items():
            decoded = iptc_tags.get(tag, str(tag))
            iptc[decoded] = value
        self.exif = exif
        self.iptc = iptc

    def make_thumbnail(self, size='m', force=False):
        self.ensure_path()
        # Construct path to thumbnail and return it if file exists
        thumbnail_path = re.sub(r'/([^/]+)$', r'/thumbs/t%s-\1' % size, self.path)
        if os.path.isfile(thumbnail_path) and os.path.getsize(thumbnail_path) > 0 and not force:
            return thumbnail_path
        # Create directory if it not exists
        thumbnail_dir = os.path.dirname(thumbnail_path)
        if not os.path.isdir(thumbnail_dir):
            os.makedirs(thumbnail_dir, 0o750)
        # Rescale and save image
        with Image.open(self.path) as image:
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
