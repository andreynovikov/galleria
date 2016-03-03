import psycopg2
import psycopg2.extras

from flask import g

import config

tbl_image = config.DB_TABLE_PREFIX + 'image'
tbl_image_label = config.DB_TABLE_PREFIX + 'label_image'
tbl_image_log = config.DB_TABLE_PREFIX + 'image_log'
tbl_image_rating = config.DB_TABLE_PREFIX + 'image_rating'
tbl_image_referrer = config.DB_TABLE_PREFIX + 'image_referrer'
tbl_label = config.DB_TABLE_PREFIX + 'label'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = psycopg2.connect(config.DB_CONNECTION_DSN)
    return db


def close():
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def commit():
    get_db().commit()


def execute(query, args=()):
    cursor = get_db().cursor()
    cursor.execute(query, args)
    try:
        result = cursor.fetchone()
    except psycopg2.ProgrammingError:
        result = None
    cursor.close()
    return result[0] if result else None


def fetch(query, args=(), one=False):
    cursor = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, args)
    if one:
        result = cursor.fetchone()
    else:
        result = cursor.fetchall()
    cursor.close()
    return result
