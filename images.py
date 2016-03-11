import os
import time
import re
from datetime import datetime
from PIL import Image, ExifTags, IptcImagePlugin

from flask import current_app

from util import diff
import db
import config

EXIF_DATE_TIME_ORIGINAL = 36867
EXIF_DATE_TIME_DIGITIZED = 36868

IPTC_OBJECT_NAME = (2, 5)
IPTC_KEYWORDS = (2, 25)
IPTC_DATE_CREATED = (2, 55)
IPTC_TIME_CREATED = (2, 60)
IPTC_BYLINE = (2, 80)

iptc_tags = {
    (1, 90): 'CodedCharacterSet',
    (2, 0): 'RecordVersion',
    IPTC_OBJECT_NAME: 'ObjectName',  # title
    IPTC_KEYWORDS: 'Keywords',
    IPTC_DATE_CREATED: 'DateCreated',
    IPTC_TIME_CREATED: 'TimeCreated',
    (2, 62): 'DigitizationDate',
    (2, 63): 'DigitizationTime',
    IPTC_BYLINE: 'Byline',  # author
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
        if image['name'] not in items:
            items[image['name']] = 0
        if items[image['name']] == 3:
            # Remove duplicates
            im = GalleriaImage.fromid(image['id'])
            im.delete(keep_file=True)
            continue
        items[image['name']] += 1
        ids[image['name']] = image['id']
    # Analyze what was found
    for name in sorted(items):
        # Image is in the directory but not in database
        if items[name] == 2:
            image = GalleriaImage.create(bundle, name)
        # Image is in the database but not in the directory
        elif items[name] == 1:
            image = GalleriaImage.fromid(ids[name])
            image.delete()
        # Image is in sync, update metadata if requested
        elif should_update_metadata:
            image = GalleriaImage.fromid(ids[name])
            image.update_metadata()


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
    @classmethod
    def create(cls, bundle, name):
        # TODO: Use gmtime instead?
        localtime = time.localtime()
        now = time.strftime("%Y-%m-%d %H:%M:%S", localtime)
        image_id = db.execute("INSERT INTO " + db.tbl_image + "(bundle, name, ctime) VALUES(%s,%s,%s) RETURNING id",
                              [bundle, name, now])
        db.commit()
        _object = cls.fromid(image_id)
        setattr(_object, 'name', name)
        setattr(_object, 'bundle', bundle)
        setattr(_object, 'ctime', now)
        _object.update_metadata()

    # noinspection SqlResolve
    def delete(self, keep_file=False):
        # db.execute("DELETE FROM " + db.tbl_image_log + " WHERE image=%s", [self.id])
        # db.execute("DELETE FROM " + db.tbl_image_rating + " WHERE image=%s", [self.id])
        # db.execute("DELETE FROM " + db.tbl_image_referrer + " WHERE image=%s", [self.id])
        db.execute("DELETE FROM " + db.tbl_image_label + " WHERE image=%s", [self.id])
        db.execute("DELETE FROM " + db.tbl_image + " WHERE id=%s", [self.id])
        db.commit()
        if not keep_file:
            # TODO: add file deletion, check existence as it can be deleted postfactum
            pass

    # noinspection SqlResolve
    def fetch_data(self):
        # do not fetch twice
        if hasattr(self, 'ctime'):
            return
        if hasattr(self, 'id'):
            # initialized by id
            data = db.fetch("SELECT * FROM " + db.tbl_image + " WHERE id=%s", [self.id], one=True)
        else:
            # initialized by path
            bundle = os.path.dirname(self.path)
            name = os.path.basename(self.path)
            bundle = bundle.replace(config.ROOT_DIR, '')
            data = db.fetch("SELECT * FROM " + db.tbl_image + " WHERE bundle=%s AND name=%s", [bundle, name], one=True)
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

    # noinspection SqlResolve
    def expand(self):
        self.fetch_data()
        # Get rating
        # cursor.execute("SELECT AVG(rating) AS average FROM " + tbl_image_rating + " WHERE image = %s GROUP BY image", [imageId])
        # rating = cursor.fetchone()
        # if rating != None:
        #    image['rating'] = rating

        # get author name
        if self.author:
            self.author_name = db.fetch("SELECT name FROM " + db.tbl_author + " WHERE id=%s", [self.author], one=True,
                                        as_list=True)

        # get labels
        labels = db.fetch(
            "SELECT id, name FROM " + db.tbl_label + " INNER JOIN " + db.tbl_image_label + " ON (label = id AND image = %s)",
            [self.id])
        if labels:
            self.labels = labels

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

    # noinspection SqlResolve
    def set_labels(self, label_names):
        assert hasattr(self, 'id'), "id must be set before fetching data"
        # select ids for each label
        labels = []
        for label_name in label_names:
            label = db.fetch("SELECT id FROM " + db.tbl_label + " WHERE name=%s", [label_name], one=True, as_list=True)
            if label is None:
                label = db.execute("INSERT INTO " + db.tbl_label + "(name) VALUES(%s) RETURNING id", [label_name])
                db.commit()
            labels.append(label)
        # get current labels
        current_labels = db.fetch("SELECT label FROM " + db.tbl_image_label + " WHERE image=%s", [self.id],
                                  as_list=True)
        # update database
        to_be_added = diff(labels, current_labels)
        to_be_deleted = diff(current_labels, labels)
        for label in to_be_added:
            db.execute("INSERT INTO " + db.tbl_image_label + "(image, label) VALUES(%s,%s)", [self.id, label])
        for label in to_be_deleted:
            db.execute("DELETE FROM " + db.tbl_image_label + " WHERE image=%s AND label=%s", [self.id, label])
            # if label is not used anymore, delete it permanently
            count = db.fetch("SELECT COUNT(image) FROM label_image WHERE label=%s", [label], one=True, as_list=True)
            if not count:
                db.execute("DELETE FROM " + db.tbl_label + " WHERE id=%s", [label])
        db.commit()
        return labels

    def update_metadata(self):
        self.open()

        iptc_info = IptcImagePlugin.getiptcinfo(self.image) or {}
        exif_info = self.image._getexif() or {}

        fields = []
        values = []

        if IPTC_OBJECT_NAME in iptc_info:
            title = iptc_info[IPTC_OBJECT_NAME].decode('utf-8')
            fields.append("description")
            values.append(title)

        timestamp = None
        if IPTC_DATE_CREATED in iptc_info and IPTC_TIME_CREATED in iptc_info:
            timestamp_str = iptc_info[IPTC_DATE_CREATED].decode('utf-8') + iptc_info[IPTC_TIME_CREATED].decode('utf-8')
            timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
        elif EXIF_DATE_TIME_ORIGINAL in exif_info:
            timestamp_str = exif_info[EXIF_DATE_TIME_ORIGINAL]
            timestamp = datetime.strptime(timestamp_str, '%Y:%m:%d %H:%M:%S')
        elif EXIF_DATE_TIME_DIGITIZED in exif_info:
            timestamp_str = exif_info[EXIF_DATE_TIME_DIGITIZED]
            timestamp = datetime.strptime(timestamp_str, '%Y:%m:%d %H:%M:%S')
        if timestamp:
            fields.append("stime")
            values.append(timestamp)

        if IPTC_BYLINE in iptc_info:
            author_name = iptc_info[IPTC_BYLINE].decode('utf-8')
            author_id = db.fetch("SELECT id FROM " + db.tbl_author + " WHERE name=%s", [author_name], one=True,
                                 as_list=True)
            if not author_id:
                author_id = db.execute("INSERT INTO " + db.tbl_author + "(name) VALUES (%s) RETURNING id",
                                       [author_name])
            fields.append("author")
            values.append(author_id)

        if IPTC_KEYWORDS in iptc_info:
            labels = []
            if isinstance(iptc_info[IPTC_KEYWORDS], list):
                for label in iptc_info[IPTC_KEYWORDS]:
                    labels.append(label.decode('utf-8'))
            else:
                labels.append(iptc_info[IPTC_KEYWORDS].decode('utf-8'))
            self.set_labels(labels)

        fields.append("width")
        values.append(self.image.width)
        fields.append("height")
        values.append(self.image.height)

        if fields:
            values.append(self.id)
            fields_str = ", ".join(map(lambda x: "%s=%%s" % x, fields))
            db.execute("UPDATE " + db.tbl_image + " SET " + fields_str + " WHERE id=%s", values)
            db.commit()

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
