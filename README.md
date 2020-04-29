# Building tarball

Make sure `setup.py` has the correct version number.

    make

will create `acnet.tgz`.

# Installing

This needs to be copied to the web server. Until this is automated,
I'm copying it with the command

    scp acnet.tgz chablis:/usr/local/www/data/pip3/acnet/acnet-VID.tgz

Replace VID with the current version number in `setup.py`. Make sure
to tag the project, too.

    git tag vVID
