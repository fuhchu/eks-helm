# eks-helm

**Project 3 of 4 — DevOps Portfolio**

Three FastAPI microservices deployed to **AWS EKS** with **Helm**, backed by a Postgres StatefulSet, fronted by an Application Load Balancer via the AWS Load Balancer Controller. Live at `https://eks-helm.fuhchu.org`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full design decisions and tradeoffs, and [docs/INTERVIEW-NOTES.md](docs/INTERVIEW-NOTES.md) for real debugging incidents hit while building this.

## Architecture

```mermaid
flowchart TD
    Internet((Internet)) -->|HTTPS 443| ALB[AWS ALB<br/>public subnets]
    ALB -->|HTTP 8000| GW[api-gateway Service<br/>2 pods]
    GW -->|HTTP 8001| Users[users Service<br/>2 pods]
    GW -->|HTTP 8002| Items[items Service<br/>2 pods]
    Items -->|validates user_id| Users
    Users --> PG[(Postgres StatefulSet<br/>EBS-backed PVC)]
    Items --> PG

    subgraph EKS Cluster
        subgraph Public Subnets
            ALB
        end
        subgraph Private Subnets
            GW
            Users
            Items
            PG
        end
    end

    CI[GitHub Actions] -->|build + push| ECR[(ECR)]
    CI -->|helm upgrade| EKS Cluster
```

## Services

| Service | Port | Responsibility |
|---------|------|----------------|
| api-gateway | 8000 | Reverse proxy; routes `/users` and `/items` |
| users | 8001 | User CRUD; owns Postgres DB |
| items | 8002 | Item CRUD; validates user existence via users svc |

## Stack

- **EKS** — managed Kubernetes control plane, IRSA (OIDC) for pod-level IAM
- **Helm** — chart packaging and release management (umbrella chart pattern)
- **AWS Load Balancer Controller** — provisions ALB + TLS from an Ingress resource
- **Postgres StatefulSet** — in-cluster database backed by an EBS-backed PVC
- **GitHub Actions** — CI/CD; path-filtered builds, git-SHA image tags, `helm upgrade --reuse-values`
- **Terraform** — VPC, EKS, ECR, IAM/IRSA, ACM, EKS Access Entries; plan/apply split with a manual approval gate

## Milestones

- [x] 0 — Repo scaffold
- [x] 1 — Terraform: EKS cluster + node group
- [x] 2 — Helm charts (per-service + umbrella)
- [x] 3 — Manual deploy: `helm install`, verify inter-service calls
- [x] 4 — Ingress + TLS (AWS LB Controller + ACM)
- [x] 5 — CI/CD: GitHub Actions → image build → `helm upgrade`
- [x] 6 — Docs + interview notes

## Related Projects

- [P1 — ECS Fargate REST API](https://github.com/fuhchu/ecs-fargate-rest-api)
- [P2 — ECS Microservices](https://github.com/fuhchu/ecs-microservices)
- P4 — EKS + GitOps (ArgoCD) + Observability — up next
