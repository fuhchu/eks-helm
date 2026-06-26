# eks-helm

**Project 3 of 4 — DevOps Portfolio**

Three FastAPI microservices deployed to **AWS EKS** with **Helm**, backed by a Postgres StatefulSet, fronted by an Application Load Balancer via the AWS Load Balancer Controller.

## Architecture

> Mermaid diagram coming in Milestone 6.

## Services

| Service | Port | Responsibility |
|---------|------|----------------|
| api-gateway | 8000 | Reverse proxy; routes `/users` and `/items` |
| users | 8001 | User CRUD; owns Postgres DB |
| items | 8002 | Item CRUD; validates user existence via users svc |

## Stack

- **EKS** — managed Kubernetes control plane
- **Helm** — chart packaging and release management
- **AWS Load Balancer Controller** — provisions ALB from Ingress resources
- **Postgres StatefulSet** — in-cluster database backed by EBS PVC
- **GitHub Actions** — CI/CD; builds images, bumps Helm values, deploys

## Milestones

- [x] 0 — Repo scaffold
- [ ] 1 — Terraform: EKS cluster + node group
- [ ] 2 — Helm charts (per-service + umbrella)
- [ ] 3 — Manual deploy: `helm install`, verify inter-service calls
- [ ] 4 — Ingress + TLS (AWS LB Controller + ACM)
- [ ] 5 — CI/CD: GitHub Actions → image build → `helm upgrade`
- [ ] 6 — Docs + interview notes

## Related Projects

- [P1 — ECS Fargate REST API](https://github.com/fuhchu/ecs-fargate-rest-api)
- [P2 — ECS Microservices](https://github.com/fuhchu/ecs-microservices)
