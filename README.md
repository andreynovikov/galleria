## Introduction

Galleria is a lightweight photo gallery application written in Python. Its main ideas are:

1. No administrative interface. everything is managed via image files
2. Photos are grouped in bundles (galleries)
3. Photos can be filtered by many criteria (tags, authors, shooting dates), also across bundles
4. Each bundle can contain hundreds of photos
5. Front-end is responsive and mobile device friendly

## Examples

Entrance page is missing but there are some life examples:

* [Huge bundle with hundreds of photos](https://andreynovikov.info/photos/travel/Georgia/2015)
* [Bundle filtered by shooting time](https://andreynovikov.info/photos/travel/Georgia/2015?-filt.from=2015-06-25;-filt.till=2015-06-26)
* [Bundle filtred by label](https://andreynovikov.info/photos/travel/Georgia/2015?-filt.labels=1)

## Dependencies

Server dependencies:

* Python3
* Postgresql (but script can be easily adopted to use another DBMS)

Python dependencies:

* Flask
* python-magic
* simplejson
* Pillow

JS dependencies:

* https://github.com/desandro/masonry
* https://github.com/aFarkas/lazysizes

## More info

* [Details](https://github.com/andreynovikov/galleria/wiki/Details)
* [Useful Links](https://github.com/andreynovikov/galleria/wiki/Useful-Links)
