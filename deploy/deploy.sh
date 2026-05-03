#!/bin/bash
set -e

DOCKER_USER="exalos"
IMAGE_NAME="neo4jtp"
TAG="latest"
FULL_IMAGE="$DOCKER_USER/$IMAGE_NAME:$TAG"

KUBECONFIG_PATH="${1:-$HOME/.kube/rancher-heia.yaml}"
CONTEXT="local"
NAMESPACE="tay-lav-adv-daba-26"
ENVIRONEMENT="PROD"
SKIP_BUILD="${SKIP_BUILD:-auto}"

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    cat <<EOF
Usage: bash deploy.sh [chemin/vers/kubeconfig.yaml]

Si aucun chemin n'est fourni, le script utilise: \$HOME/.kube/rancher-heia.yaml

Exemples:
  bash deploy.sh
  bash deploy.sh ~/Downloads/local.yaml
  bash deploy.sh /c/Users/Plus/Downloads/local.yaml

Variables d'environnement optionnelles:
  SKIP_BUILD=true    # force à ne pas builder l'image Docker
  SKIP_BUILD=false   # force le build (échoue si docker absent)
  SKIP_BUILD=auto    # (défaut) auto-détecte la présence de docker
EOF
    exit 0
fi

# Auto-detect Docker if SKIP_BUILD=auto
if [[ "$SKIP_BUILD" == "auto" ]]; then
    if command -v docker >/dev/null 2>&1; then
        SKIP_BUILD="false"
    else
        echo "[INFO] Docker non détecté → SKIP_BUILD activé automatiquement"
        SKIP_BUILD="true"
    fi
fi

if [[ "$SKIP_BUILD" != "true" ]]; then
    echo "Build"
    docker build -t $FULL_IMAGE ../loader

    echo "Push"
    docker push $FULL_IMAGE
else
    echo "[SKIP_BUILD] On utilise l'image $FULL_IMAGE depuis Docker Hub"
fi

if [[ "$ENVIRONEMENT" == "DEV" ]]; then
    if ! command -v minikube >/dev/null 2>&1; then
        echo "[ERROR] minikube n'est pas installé." >&2
        exit 1
    fi
    if ! minikube status >/dev/null 2>&1; then
        minikube start --nodes 2 --driver=docker
    fi
    kubectl config use-context minikube
else
    if [[ ! -f "$KUBECONFIG_PATH" ]]; then
        echo "[ERROR] Kubeconfig introuvable: $KUBECONFIG_PATH" >&2
        echo "        Télécharge-le depuis Rancher (Cluster Management → Download KubeConfig)" >&2
        echo "        et place-le à cet emplacement." >&2
        exit 1
    fi
    export KUBECONFIG="$KUBECONFIG_PATH"
    kubectl config use-context $CONTEXT
    kubectl config set-context --current --namespace=$NAMESPACE
fi

echo "Nettoyage"
kubectl delete job neo4jtp-loader --ignore-not-found

echo "Déploiement Neo4j..."
kubectl apply -f neo4j-pvc.yaml
kubectl apply -f neo4j-deployment.yaml
kubectl apply -f neo4j-service.yaml

echo "Attente que Neo4j soit Ready..."
kubectl wait --for=condition=Available deployment/neo4j-deployment --timeout=180s

echo "Lancement du Job de chargement..."
kubectl apply -f loader-job.yaml
kubectl port-forward svc/neo4j-service 7474:7474 7687:7687 >/dev/null 2>&1 &

echo "Monitoring des logs..."
kubectl wait --for=condition=Ready pod -l app=loader --timeout=120s
kubectl logs -f job/neo4jtp-loader
