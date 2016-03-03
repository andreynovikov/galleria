import os
import io
import magic
import simplejson as json
from PIL import Image

from flask import Flask, Response, request, render_template, send_file, abort

from images import sync_bundle, make_thumbnail
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/<path:path_info>')
def galleria(path_info):
    bundle_path = None
    image_path = None

    path = ''.join([config.ROOT_DIR, '/', path_info])
    app.logger.debug("Path: %s" % path)
    if os.path.isfile(path):
        image_path = path
    elif os.path.isdir(path):
        bundle_path = '/' + path_info

    action = request.args.get('action', None)
    image_format = request.args.get('format', None)
    image_id = request.args.get('id', None)

    app.logger.debug("Action: %s" % action)

    if image_path is not None:
        if image_format == 'original':
            response = original(image_path)
        else:
            response = view(image_path, image_format)
    elif action == 'list':
        response = select(bundle_path)
    elif action == 'thumbnail':
        size = request.args.get('size', 'm')
        force = bool(request.args.get('force', None))
        response = thumbnail(image_id, size, force)
    else:
        query_string = request.query_string.decode('utf-8')
        response = render_template('show.html', request=request, config=config, bundle=bundle_path, query_string=query_string)

    """
    elif action == 'info':
        response = info(request, image_id)
    elif action == 'log':
        response = log(request, image_id)
    elif action == 'env':
        response = Response(content_type='text/plain', charset='utf-8')
        parts = []
        for name, value in sorted(request.environ.items()):
            parts.append('%s: %r' % (name, value))
        response.text = '\n'.join(parts)
    elif not action is None:
        response = Response(content_type='text/plain', charset='utf-8')
        response.text = 'Unknown action'
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
    response.headers.add('Access-Control-Allow-Origin', 'http://andreynovikov.info')
    return response


@app.errorhandler(413)
def bad_query(error):
    return 'Query should be more specific', error


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
        having.extend(map(lambda x: 'SUM(IF(label=%s,1,0)) > 0' % x, labels.split(',')))
        join = 'INNER JOIN ' + db.tbl_image_label + ' ON (id = image)'
        group = 'image'
    if notlabels:
        should_sync_bundle = False
        # todo: where clause should not be added twice
        where.append(db.tbl_image_label + '.label IS NOT NULL')
        having.extend(map(lambda x: 'SUM(IF(label=%s,1,0)) = 0' % x, notlabels.split(',')))
        join = 'INNER JOIN ' + db.tbl_image_label + ' ON (id = image)'
        group = 'image'

    censored = request.args.get('-filt.censored', None)
    if censored:
        where.append('censored = %s' % censored)
    elif not request.args.get('any', None) and (not labels or '424' not in labels.split(',')):
        where.append('censored = 0')

    if bundle:
        where.append('bundle = \'%s\'' % bundle)
    sfrom = request.args.get('-filt.from', None)
    if sfrom:
        should_sync_bundle = False
        where.append('stime >= %s' % sfrom)

    still = request.args.get('-filt.till', None)
    if still:
        should_sync_bundle = False
        where.append('stime <= %s' % still)

    if should_sync_bundle:
        path = ''.join([config.ROOT_DIR, bundle])
        sync_bundle(path, bundle)

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

    response = Response(response=json.dumps(images, indent=4, ensure_ascii=False),
                        status=200, mimetype='application/json')
    return response


def view(image_path, image_format):
    export = image_format == 'export'

    image = Image.open(image_path)

    fmt = image.format
    ox = image.width
    oy = image.height
    rx = config.SCREEN_MAX_WIDTH
    ry = config.SCREEN_MAX_HEIGHT

    if export:
        rx = config.EXPORT_MAX_WIDTH
        ry = config.EXPORT_MAX_HEIGHT

    nx = rx
    ny = ry
    if ox > oy:
        ny = int(oy / ox * nx)
    else:
        nx = int(ox / oy * ny)

    if ox > int(nx * config.SCREEN_DELTA) or oy > int(ny * config.SCREEN_DELTA):
        image = image.resize((nx, ny), Image.LANCZOS)

    b = io.BytesIO()
    image.save(b, format=fmt)
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
    response.set_etag(etag)

    return response


def original(image_path):
    mime_type = magic.from_file(image_path, mime=True).decode('utf-8')
    # cache for one month
    response = send_file(image_path, mimetype=mime_type, cache_timeout=2592000,
                         conditional=True, as_attachment=True, add_etags=True)
    response.content_length = os.path.getsize(image_path)
    response.last_modified = os.path.getmtime(image_path)
    return response


@app.route('/thumbnail/<int:image_id>')
def thumbnail(image_id):
    size = request.args.get('size', 'm')
    force = bool(request.args.get('force', None))

    # noinspection SqlResolve
    image = db.fetch("SELECT name, bundle FROM " + db.tbl_image + " WHERE id=%s", [image_id], True)

    path = ''.join([config.ROOT_DIR, image['bundle'], '/', image['name']])
    thumbnail_path = make_thumbnail(path, size, force)

    # add_log(request, db, image_id, 4)

    mime_type = magic.from_file(thumbnail_path, mime=True).decode('utf-8')
    # cache for one month
    response = send_file(thumbnail_path, mimetype=mime_type, cache_timeout=2592000,
                         conditional=True, add_etags=True)
    response.content_length = os.path.getsize(thumbnail_path)
    response.last_modified = os.path.getmtime(thumbnail_path)
    return response


if __name__ == '__main__':
    app.run()
