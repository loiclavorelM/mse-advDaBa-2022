#!/bin/bash
set -e

DOCKER_USER="exalos"    
IMAGE_NAME="neo4jtp"
TAG="latest"
FULL_IMAGE="$DOCKER_USER/$IMAGE_NAME:$TAG"

NAMESPACE="adv-da-ba26-tonnom"
ENVIRONEMENT="DEV"

echo "Build"
docker build -t $FULL_IMAGE ../loader

echo "Push"
docker push $FULL_IMAGE

if [[ "$ENVIRONEMENT" == "DEV" ]]; then
    if ! minikube status >/dev/null 2>&1; then
        minikube start --nodes 2 --driver=docker
    fi
    kubectl config use-context minikube
else
    kubectl config use-context $NAMESPACE
    kubectl config set-context --current --namespace=$NAMESPACE
fi

echo "Nettoyage"
kubectl delete job neo4jtp-loader --ignore-not-found

echo "Déploiement"
kubectl apply -f neo4j-pvc.yaml
kubectl apply -f neo4j-deployment.yaml
kubectl apply -f neo4j-service.yaml

echo "Attente du démarrage de Neo4j (30s)..."
sleep 30

echo "Lancement du Job de chargement..."
kubectl apply -f loader-job.yaml
kubectl port-forward svc/neo4j-service 7474:7474 7687:7687 >/dev/null 2>&1 &

echo " Monitoring des logs..."
kubectl wait --for=condition=Ready pod -l app=loader --timeout=60s
kubectl logs -f job/neo4jtp-loader