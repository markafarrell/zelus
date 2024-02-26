
# Test Helm chart
```
docker stop k3s-zelus-route-manager
sudo rm -rf container-data/
mkdir -p container-data/

docker run --rm -dt \
    --name k3s-zelus-route-manager \
    -v ${PWD}/container-data/etc/rancher/k3s:/etc/rancher/k3s \
    -e K3S_TOKEN=123456 \
    -e K3S_KUBECONFIG_MODE=666 \
    -e no_proxy=localhost,127.0.0.1,172.0.0.0/8 \
    -p 6443:6443 \
    --privileged \
    harbor.tools.telstra.com/public-cache/rancher/k3s:v1.23.14-k3s1 server

helm package charts/zelus-route-manager
export KUBECONFIG=${PWD}/container-data/etc/rancher/k3s/k3s.yaml

helm install -n zelus --create-namespace zelus zelus-route-manager-0.0.1.tgz
```

# Installing Helm Chart

```
helm repo add zelus https://markafarrell.github.io/zelus/
helm search repo zelus
helm install -n zelus --create-namespace zelus zelus/zelus-route-manager

helm upgrade -n zelus --create-namespace zelus zelus/zelus-route-manager
```

