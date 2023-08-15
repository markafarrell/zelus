# zelus

## Requrements

```
python >= 3.8
iproute2
```

## Initialize build environment

```
python -m pip install -U setuptools wheel build
```

## Build python package

```
python -m build .
```

## Building docker image

```
docker build -t markfarrell/zelus .
```

## Running docker container

```
docker build -t markfarrell/zelus . && \
docker run --rm -it --name zelus --cap-add NET_ADMIN markfarrell/zelus
```

### Exec into container

```
docker exec -it zelus /bin/sh
```

## Testing

### Lint

```
tox -e lint
```

