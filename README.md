## Introduction

Galleria is a lightweight photo gallery application written in Python. The main ideas behind it are:

1. No administrative interface, everything is managed via image files.
2. Photos are grouped in bundles (galleries).
3. Photos can be filtered by many criteria (tags, authors, shooting dates), also across bundles.
4. Each bundle can contain hundreds of photos.
5. Front-end is responsive and mobile device friendly.
6. Friendly URLs for easy blogging.

## Examples

* [Entrance page with selection by label](https://andreynovikov.info/photos/index)
* [Huge bundle with hundreds of photos](https://andreynovikov.info/photos/travel/Georgia/2015)
* [Bundle filtered by shooting time](https://andreynovikov.info/photos/travel/Georgia/2015?-filt.from=2015-06-25;-filt.till=2015-06-26)
* [All photos filtered by label](https://andreynovikov.info/photos/?-filt.labels=1)
* [Single photo, original image file, huge](https://andreynovikov.info/photos/travel/Georgia/2015/IMG_2171.JPG?format=original)
* [Single photo, optimized](https://andreynovikov.info/photos/travel/Georgia/2015/IMG_2171.JPG)
* [Single thumbnail](https://andreynovikov.info/photos/travel/Georgia/2015/IMG_2171.JPG?format=thumbnail)

Last two examples are useful for blogging – photos can be inserted in text as if they are static.

## Dependencies

Server dependencies:

* Python3
* Postgresql (but script can be easily adopted to use another DBMS)

Python dependencies:

* Flask
* python-magic
* Pillow

JS dependencies:

* https://github.com/desandro/masonry
* https://github.com/aFarkas/lazysizes

## More info

* [Details](https://github.com/andreynovikov/galleria/wiki/Details)
* [Useful Links](https://github.com/andreynovikov/galleria/wiki/Useful-Links)
