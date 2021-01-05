# ACSYS Python DPM Client

## Building tarball

Make sure `setup.py` has the correct version number.

    make

will create `acsys.tgz`.

## Installing

This needs to be copied to the web server. Until this is automated,
I'm copying it with the command

    scp acsys.tgz chablis:/usr/local/www/data/pip3/acsys/acsys-VID.tgz

Replace VID with the current version number in `setup.py`. Make sure
to tag the project, too.

    git tag vVID

## Development

To test local modifications, use pip's editable mode.

`pip install -e .`
