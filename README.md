# ACSys Python DPM Client

`acsys` is the interface to Fermilab data acquisition and control.

## Installing

`acsys` is available via a Fermi hosted pip repository.

```bash
python3 -m pip install acsys --extra-index-url=https://www-bd.fnal.gov/pip3
```

The command above will get you up and going quickly. See usage examples in the [wiki](https://github.com/fermi-controls/acsys-python/wiki).

If you need to perform settings, authentication is required and thus the `gssapi` authentication library.

```bash
python3 -m pip install 'acsys[settings]' --extra-index-url=https://www-bd.fnal.gov/pip3
```

Note: This package only authenticates you as a user. There are other requirements to be able to set devices. Please make a request to the Controls Department for setting access.

## Building

Make sure `setup.py` has the correct version number.

```bash
make
```

will create a source distribution at `./dist`.

This should only be used for development.

```bash
make all
```

The above will generate "built distributions" as well as the source distributions from `make`.

## Deploying

```bash
make deploy
```

The above will generate the distributions and push them to the AD Controls pip server.

## Development

Start by installing development dependencies.

```bash
pip install -r requirements.txt
```

To test local modifications, use pip's editable mode.

`pip install -e .`

Make sure to use git to tag the version.

```bash
git tag vVID
```

And push the tags.

```bash
git push --tags
```
