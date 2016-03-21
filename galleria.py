import os
import io
import re
import magic
from PIL import Image

from flask import Flask, request, render_template, send_file, redirect, abort, jsonify, url_for

from images import sync_bundle, check_bundle, get_related_labels, GalleriaImage
from util import to_list, ip2int
import db
import config


class QueryStringRedirectMiddleware(object):
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        environ['QUERY_STRING'] = qs.replace(';', '&')
        return self.application(environ, start_response)


app = Flask(__name__)
app.debug = True
app.wsgi_app = QueryStringRedirectMiddleware(app.wsgi_app)
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True


@app.route('/', defaults={'path_info': None})
@app.route('/<path:path_info>')
def galleria(path_info):
    bundle_path = ''
    image_path = None

    if path_info:
        # normalize path_info
        path_info = path_info.rstrip('/')
        path_info = re.sub('/+\.*', '/', path_info)
        # select target and action
        path = '/'.join([config.ROOT_DIR, path_info])
        if '/thumbs' in path_info:
            abort(403)
        elif os.path.isfile(path):
            image_path = path
        elif os.path.isdir(path):
            bundle_path = '/' + path_info
        else:
            check_bundle('/' + path_info)
            abort(404)

    action = request.args.get('action', None)

    if image_path:
        image_format = request.args.get('format', None)
        if image_format == 'original':
            response = original(image_path)
        elif image_format == 'thumbnail':
            # helper method for manually linking to thumbnails
            image = GalleriaImage.frompath(image_path)
            image.fetch_data()
            response = thumbnail(image.id)
        else:
            ratio = float(request.args.get('ratio', '1.0'))
            response = view(image_path, image_format, ratio)
    elif action == 'list':
        response = select(bundle_path)
    elif action is not None:
        response = 'Unknown action'
    elif bundle_path or request.args:
        query_string = request.query_string.decode('utf-8')
        if bundle_path:
            query = bundle_path
        else:
            query = '/'
        if query_string:
            query = query + '?' + query_string
        response = render_template('show.html', config=config, query=query)
    else:
        response = redirect(url_for('index'))

    """
    elif action == 'log':
        response = log(request, image_id)
    """

    # response.cache_control.private = True
    # response.vary = ['Cookie']
    # print >> sys.stderr, response
    # for name, value in response.headerlist:
    #    print >> sys.stderr, '%s: %s' % (name, value)

    return response


@app.teardown_request
def teardown_request(exception):
    db.close()


@app.after_request
def after_request(response):
    # TODO: Make configurable
    response.headers.add('Access-Control-Allow-Origin', 'https://andreynovikov.info')
    return response


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(413)
def bad_query(error):
    return 'Query should be more specific', error


@app.template_test()
def equalto(value, other):
    return value == other


def select(bundle):
    should_sync_bundle = bundle is not None
    where = []
    having = []
    join = None
    group = None
    order = request.args.get('-nav.order', 'stime')
    labels = request.args.get('-filt.labels', None)
    notlabels = request.args.get('-filt.notlabels', None)
    if labels:
        should_sync_bundle = False
        where.append(db.tbl_image_label + '.label IS NOT NULL')
        # mysql syntax: SUM(IF(label=%s,1,0)) > 0
        having.extend(map(lambda x: 'SUM(CASE WHEN label=%s THEN 1 ELSE 0 END) > 0' % x, labels.split(',')))
        join = 'INNER JOIN ' + db.tbl_image_label + ' ON (id = image)'
        group = 'id'
    if notlabels:
        should_sync_bundle = False
        # todo: where clause should not be added twice
        where.append(db.tbl_image_label + '.label IS NOT NULL')
        # mysql syntax: SUM(IF(label=%s,1,0)) = 0
        having.extend(map(lambda x: 'SUM(CASE WHEN label=%s THEN 1 ELSE 0 END) = 0' % x, notlabels.split(',')))
        join = 'INNER JOIN ' + db.tbl_image_label + ' ON (id = image)'
        group = 'id'

    censored = request.args.get('-filt.censored', None)
    if censored is not None:
        should_sync_bundle = False
        where.append('censored = %s' % censored)
    elif not request.args.get('any', None) and (not labels or '424' not in labels.split(',')):
        where.append('censored = 0')

    if bundle:
        where.append('bundle = \'%s\'' % bundle)
    sfrom = request.args.get('-filt.from', None)
    if sfrom:
        should_sync_bundle = False
        where.append('stime >= \'%s\'' % sfrom)

    still = request.args.get('-filt.till', None)
    if still:
        should_sync_bundle = False
        where.append('stime <= \'%s\'' % still)

    if should_sync_bundle:
        path = ''.join([config.ROOT_DIR, bundle])
        should_update_metadata = bool(request.args.get('updatemetadata', None))
        sync_bundle(path, bundle, should_update_metadata)

    # noinspection SqlResolve
    query = 'SELECT id, name, bundle, description, width, height FROM ' + db.tbl_image
    qlen = len(query)

    if join:
        query += ' '
        query += join

    if where:
        query += ' WHERE '
        query += ' AND '.join(where)

    if group:
        query += ' GROUP BY '
        query += group

    if having:
        query += ' HAVING '
        query += ' AND '.join(having)

    if len(query) == qlen:
        abort(413)

    query += ' ORDER BY '
    query += order
    app.logger.debug("Query: %s" % query)

    images = db.fetch(query)

    for image in images:
        image['path'] = ''.join([request.script_root, image['bundle'], '/', image['name']])

    return jsonify(images=images)
    # response = Response(response=json.dumps(images, indent=4, ensure_ascii=False),
    #                     status=200, mimetype='application/json; charset=utf-8')
    # return response


def view(image_path, image_format, ratio=1.0):
    export = image_format == 'export'
    image = GalleriaImage.frompath(image_path)
    image.fetch_data()
    image.open()

    fmt = image.image.format
    ox = image.image.width
    oy = image.image.height
    nx = config.SCREEN_MAX_WIDTH
    ny = config.SCREEN_MAX_HEIGHT

    if export:
        nx = config.EXPORT_MAX_WIDTH
        ny = config.EXPORT_MAX_HEIGHT
        log(request, image.id, db.LOG_STATUS_EXPORT)
    else:
        log(request, image.id, db.LOG_STATUS_VIEW)

    if ratio < 1:
        nx = int(nx * ratio)
        ny = int(ny * ratio)

    if ox > oy:
        ny = int(oy / ox * nx)
    else:
        nx = int(ox / oy * ny)

    if ox > int(nx * config.SCREEN_DELTA) or oy > int(ny * config.SCREEN_DELTA):
        im = image.image.resize((nx, ny), Image.LANCZOS)
    else:
        im = image.image

    b = io.BytesIO()
    im.save(b, format=fmt)
    b.seek(0)
    mime_type = magic.from_buffer(b.read(1024), mime=True).decode('utf-8')
    b.seek(0)

    # cache for one month
    response = send_file(b, mimetype=mime_type, attachment_filename=os.path.basename(image_path),
                         cache_timeout=2592000, conditional=True, add_etags=True)
    response.content_length = b.getbuffer().nbytes
    response.last_modified = os.path.getmtime(image_path)
    etag = image_path
    etag = etag.replace(config.ROOT_DIR, '')
    etag = etag.replace('.', '_')
    etag = etag.replace('/', '__')
    if ratio:
        etag = etag + '__' + str(ratio)
    response.set_etag(etag)

    return response


def original(image_path):
    image = GalleriaImage.frompath(image_path)
    image.fetch_data()
    log(request, image.id, db.LOG_STATUS_ORIGINAL)
    mime_type = magic.from_file(image_path, mime=True).decode('utf-8')
    # cache for one month
    response = send_file(image_path, mimetype=mime_type, cache_timeout=2592000,
                         conditional=True, as_attachment=True, add_etags=True)
    response.content_length = os.path.getsize(image_path)
    response.last_modified = os.path.getmtime(image_path)
    return response


# noinspection SqlResolve
@app.route('/index')
def index():
    bundles = db.fetch("SELECT bundle AS path, COUNT(id) AS count FROM " + db.tbl_image + " GROUP BY bundle ORDER BY path")
    current_labels = to_list(request.args.get('labels', None))
    current_not_labels = to_list(request.args.get('notlabels', None))
    related_labels = get_related_labels(current_labels, current_not_labels)
    labels = db.fetch("SELECT id, name, COUNT(image) AS count FROM " + db.tbl_label + " INNER JOIN " +
                      db.tbl_image_label + " ON (label = id) GROUP BY id ORDER BY name ASC")
    return render_template('index.html', config=config, bundles=bundles, labels=labels,
                           current_labels=current_labels, current_not_labels=current_not_labels,
                           related_labels=related_labels)


@app.route('/thumbnail/<int:image_id>')
def thumbnail(image_id):
    size = request.args.get('size', 'm')
    force = bool(request.args.get('force', None))

    image = GalleriaImage.fromid(image_id)
    thumbnail_path = image.make_thumbnail(size, force)

    log(request, image_id, db.LOG_STATUS_THUMBNAIL)

    mime_type = magic.from_file(thumbnail_path, mime=True).decode('utf-8')
    # cache for one month
    response = send_file(thumbnail_path, mimetype=mime_type, cache_timeout=2592000,
                         conditional=True, add_etags=True)
    response.content_length = os.path.getsize(thumbnail_path)
    response.last_modified = os.path.getmtime(thumbnail_path)
    return response


@app.route('/info/<int:image_id>')
def info(image_id):
    image = GalleriaImage.fromid(image_id)
    image.expand()
    log(request, image_id, db.LOG_STATUS_INFO)
    return jsonify(image.get_data(request.script_root), ensure_ascii=True)


def log(request, image_id, status):
    user_id = ip2int(request.remote_addr)
    db.execute("INSERT INTO " + db.tbl_image_log + " VALUES(%s, %s, %s, NOW())", (image_id, user_id, status))
    db.commit()


if __name__ == '__main__':
    app.run()
