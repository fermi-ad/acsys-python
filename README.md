# ACSys Python DPM Client

`acsys` is the interface to Fermilab data acquisition and control.

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
