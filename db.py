import click
import psycopg2
import psycopg2.extras

from flask import g, current_app
from flask.cli import with_appcontext

import config


tbl_image = config.DB_TABLE_PREFIX + 'image'
tbl_image_label = config.DB_TABLE_PREFIX + 'label_image'
tbl_image_log = config.DB_TABLE_PREFIX + 'log'
tbl_image_rating = config.DB_TABLE_PREFIX + 'image_rating'
tbl_image_referrer = config.DB_TABLE_PREFIX + 'image_referrer'
tbl_label = config.DB_TABLE_PREFIX + 'label'
tbl_author = config.DB_TABLE_PREFIX + 'author'

LOG_STATUS_ORIGINAL = 0
LOG_STATUS_VIEW = 1
LOG_STATUS_INFO = 2
LOG_STATUS_EXPORT = 3
LOG_STATUS_THUMBNAIL = 4


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        if current_app.debug:
            db = psycopg2.connect(config.DB_CONNECTION_DSN, connection_factory=psycopg2.extras.LoggingConnection)
            db.initialize(current_app.logger)
        else:
            db = psycopg2.connect(config.DB_CONNECTION_DSN)
        g._database = db
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


def fetch(query, args=(), one=False, as_list=False):
    """
    Fetches data from database

    :param query: SQL query
    :param args: Arguments for SQL query
    :param one: If `true` only first row is fetched
    :param as_list: If `true` data is fetched as array, otherwise dictionary is used, useful only with one-column query
    :return: Single value, or list of values (column), or dictionary or list of dictionaries
    """
    if as_list:
        cursor = get_db().cursor()
    else:
        cursor = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, args)
    if one:
        result = cursor.fetchone()
    else:
        result = cursor.fetchall()
    cursor.close()
    if result is None:
        return None
    elif one and as_list:
        return result[0]
    elif as_list:
        return [element for (element,) in result]
    else:
        return result


def init_db():
    db = get_db()
    with db.cursor() as cursor, current_app.open_resource('schema.sql') as f:
        cursor.execute(f.read().decode('utf8'))
        db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()
    click.echo('Initialized the database.')
