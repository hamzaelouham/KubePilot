#4a5ee7 header  
#f5f7f9 background

docker pull hamzaelouham/kubepilot-ui:latest hamzaelouham/kubepilot-backend:latest
minikube image load kubepilot-backend:latest kubepilot-ui:latest
minikube kubectl -- apply -f backend/deploy/kubernetes/
minikube service kubepilot-ui -n kubepilot
