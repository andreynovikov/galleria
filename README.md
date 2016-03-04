﻿Galleria is a lightweight photo gallery application written in Python. Its main ideas are:

1. No administrative interface. everything is managed via image files
2. Photos are grouped in bundles (galleries)
3. Photos can be filtered by many criteria (tags, authors, shooting dates), also across bundles
4. Each bundle can contain hundreds of photos
5. Front-end is responsive and mobile device friendly

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

* [Details](https://github.com/andreynovikov/galleria/wiki/Details)
* [Useful Links](https://github.com/andreynovikov/galleria/wiki/Useful-Links)
