# AI Catalogue - Kubernetes Deployment

This directory contains Kubernetes manifests and deployment scripts for running AI Catalogue on Kubernetes, with specific support for Azure Kubernetes Service (AKS).

## 📁 Directory Structure

```
k8s/
├── base/                    # Base Kubernetes manifests
│   ├── namespace.yaml       # Namespaces (prod & dev)
│   ├── configmap.yaml       # Configuration maps
│   ├── secrets.yaml         # Secrets management
│   ├── postgres.yaml        # PostgreSQL database
│   ├── milvus.yaml         # Milvus vector DB + dependencies
│   ├── backend.yaml        # Django backend application
│   ├── frontend.yaml       # SvelteKit frontend
│   ├── management-ui.yaml  # PgAdmin & Attu management UIs
│   └── ingress.yaml        # Ingress configuration
├── scripts/                # Deployment scripts
│   ├── k8s-start.sh        # Production deployment
│   ├── k8s-start-dev.sh    # Development deployment
│   ├── k8s-stop.sh         # Stop/cleanup script
│   └── azure-setup.sh      # Azure infrastructure setup
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Prerequisites

- **kubectl** installed and configured
- **Docker** for building images
- **Azure CLI** (for Azure deployment)
- **.env** file configured with your settings

### 2. Local Kubernetes Development

```bash
# Start development environment
./k8s/scripts/k8s-start-dev.sh

# Access services via port-forwarding
kubectl port-forward -n ai-catalogue-dev service/frontend-service 3000:3000
kubectl port-forward -n ai-catalogue-dev service/backend-service 8000:8000
```

### 3. Azure Production Deployment

```bash
# Setup Azure infrastructure (one-time)
./k8s/scripts/azure-setup.sh

# Build and push images
docker build -t your-registry.azurecr.io/ai-catalogue-backend:latest ./backend
docker build -t your-registry.azurecr.io/ai-catalogue-frontend:latest ./frontend
docker push your-registry.azurecr.io/ai-catalogue-backend:latest
docker push your-registry.azurecr.io/ai-catalogue-frontend:latest

# Deploy to production
./k8s/scripts/k8s-start.sh
```

## ⚙️ Configuration

### Environment Variables

The deployment uses your existing `.env` file with additional Kubernetes-specific variables:

```bash
# Kubernetes Configuration
K8S_NAMESPACE=ai-catalogue
CONTAINER_REGISTRY=your-registry.azurecr.io
IMAGE_TAG=latest
STORAGE_CLASS_NAME=managed-premium
DOMAIN_NAME=your-domain.com

# Azure Configuration  
AZURE_RESOURCE_GROUP=rg-ai-catalogue
AKS_CLUSTER_NAME=aks-ai-catalogue
AZURE_CONTAINER_REGISTRY=aicatalogueacr
```

### Service Architecture

The Kubernetes deployment mirrors your Docker Compose setup:

- **PostgreSQL**: Database with persistent storage
- **Etcd**: Metadata store for Milvus
- **MinIO**: Object storage for Milvus
- **Milvus**: Vector database for AI search
- **Backend**: Django application server
- **Frontend**: SvelteKit web application
- **PgAdmin**: Database management UI
- **Attu**: Milvus management UI
- **Ingress**: External access with SSL termination

## 🔧 Management Commands

### Deployment Commands

```bash
# Production deployment
./k8s/scripts/k8s-start.sh

# Development deployment  
./k8s/scripts/k8s-start-dev.sh

# Stop and cleanup
./k8s/scripts/k8s-stop.sh

# Setup Azure infrastructure
./k8s/scripts/azure-setup.sh
```

### Monitoring Commands

```bash
# Check pod status
kubectl get pods -n ai-catalogue

# View logs
kubectl logs -n ai-catalogue deployment/backend -f
kubectl logs -n ai-catalogue deployment/frontend -f

# Scale deployments
kubectl scale deployment backend --replicas=5 -n ai-catalogue

# Port forward for local access
kubectl port-forward -n ai-catalogue service/frontend-service 3000:3000
```

### Database Management

```bash
# Connect to PostgreSQL
kubectl exec -it -n ai-catalogue deployment/postgres -- psql -U ai_catalogue_user -d ai_catalogue_db

# Backup database
kubectl exec -n ai-catalogue deployment/postgres -- pg_dump -U ai_catalogue_user ai_catalogue_db > backup.sql

# Access PgAdmin
kubectl port-forward -n ai-catalogue service/pgadmin-service 8080:8080
# Open http://localhost:8080
```

## 🔐 Security Features

### Network Security
- **Network Policies**: Restrict pod-to-pod communication
- **Ingress Controller**: NGINX with SSL termination
- **Secrets Management**: Kubernetes secrets for sensitive data

### Access Control
- **RBAC**: Role-based access control
- **Service Accounts**: Dedicated service accounts per component
- **Pod Security**: Non-root containers with security contexts

### SSL/TLS
- **cert-manager**: Automatic SSL certificate management
- **Let's Encrypt**: Free SSL certificates
- **Force HTTPS**: Automatic HTTP to HTTPS redirects

## 📊 Scaling & Performance

### Horizontal Pod Autoscaling
Automatic scaling based on CPU and memory usage:

```yaml
# Backend autoscaling: 2-10 replicas
# Frontend autoscaling: 2-5 replicas
# Triggers: 70% CPU or 80% memory
```

### Resource Limits
Production resource allocation:

```yaml
Backend:  1-2 GB RAM, 0.5-1 CPU
Frontend: 256-512 MB RAM, 0.25-0.5 CPU  
PostgreSQL: 512MB-1GB RAM, 0.25-0.5 CPU
Milvus: 1-2 GB RAM, 0.5-1 CPU
```

### Storage
- **Persistent Volumes**: Managed Azure Disks
- **Storage Classes**: Premium SSD for production
- **Backup Strategy**: Automated snapshots

## 🌐 Azure Integration

### Managed Services
- **Azure Database for PostgreSQL**: Managed database service
- **Azure Container Registry**: Private container images
- **Azure Key Vault**: Secrets management
- **Azure Monitor**: Logging and monitoring

### Network Architecture
- **Application Gateway**: L7 load balancer with WAF
- **Virtual Network**: Isolated network environment
- **Private Endpoints**: Secure service connections

## 🚨 Troubleshooting

### Common Issues

1. **Pods stuck in Pending**: Check resource quotas and node capacity
2. **ImagePullBackOff**: Verify container registry credentials
3. **CrashLoopBackOff**: Check application logs and configuration
4. **Ingress not working**: Verify DNS configuration and SSL certificates

### Debug Commands

```bash
# Describe pod issues
kubectl describe pod <pod-name> -n ai-catalogue

# Check events
kubectl get events -n ai-catalogue --sort-by=.metadata.creationTimestamp

# Check ingress
kubectl describe ingress ai-catalogue-ingress -n ai-catalogue

# Test connectivity
kubectl run debug --image=busybox -it --rm --restart=Never -- sh
```

### Log Analysis

```bash
# Application logs
kubectl logs -n ai-catalogue -l app=backend --tail=100

# System logs (if using Azure Monitor)
az monitor log-analytics query \
  --workspace ai-catalogue-logs \
  --analytics-query "ContainerLog | where ContainerName == 'backend'"
```

## 🔄 Updates & Maintenance

### Rolling Updates
```bash
# Update backend image
kubectl set image deployment/backend backend=your-registry/ai-catalogue-backend:new-tag -n ai-catalogue

# Check rollout status
kubectl rollout status deployment/backend -n ai-catalogue

# Rollback if needed
kubectl rollout undo deployment/backend -n ai-catalogue
```

### Maintenance Windows
```bash
# Drain node for maintenance
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Uncordon after maintenance
kubectl uncordon <node-name>
```

## 💡 Best Practices

1. **Resource Quotas**: Set namespace resource limits
2. **Monitoring**: Use Prometheus + Grafana for metrics
3. **Backup Strategy**: Regular database and PVC backups
4. **Security Scanning**: Scan container images for vulnerabilities
5. **CI/CD Integration**: Automate deployments via GitHub Actions
6. **Disaster Recovery**: Multi-region deployment for high availability

## 📞 Support

- **Logs**: Check application and system logs first
- **Documentation**: Refer to Kubernetes and Azure documentation
- **Community**: Kubernetes and Azure community forums
- **Monitoring**: Use Azure Monitor for production issues

---

🎉 **Your AI Catalogue is now ready for enterprise Kubernetes deployment!**