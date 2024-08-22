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
docker run --rm -it --name zelus --volume $(pwd)/docker-data/etc/zelus:/etc/zelus --cap-add NET_ADMIN -p 9123:9123 markfarrell/zelus --interface eth0 --mode=strict
```

### Exec into container

```
docker exec -it zelus /bin/sh
```

### Test prometheus metrics

```
curl http://localhost:9123/metrics
```

## Testing

### Lint

```
tox -e lint
```

