# Architecture

## Overview

Three FastAPI microservices deployed to AWS EKS, packaged with Helm, exposed via an
AWS ALB with TLS, and deployed automatically through GitHub Actions CI/CD.

```
Internet
   │
   ▼ HTTPS (443, ACM cert for eks-helm.fuhchu.org)
AWS Application Load Balancer (public subnets)
   │  provisioned by AWS Load Balancer Controller from an Ingress resource
   ▼ HTTP (8000)
api-gateway Service (ClusterIP) → 2x api-gateway pods
   │
   ├─→ users Service (ClusterIP, :8001) → 2x users pods ─┐
   │                                                       ▼
   └─→ items Service (ClusterIP, :8002) → 2x items pods → postgres-0 (StatefulSet, EBS-backed)
```

All app pods and the node group run in **private subnets** — no public IPs. Outbound
traffic (pulling images from ECR) goes through a single NAT Gateway.

## Why EKS over ECS (Project 1/2 used ECS)

ECS is AWS-proprietary; EKS is standard Kubernetes. The skills transfer to any cloud
or on-prem cluster. Tradeoff: EKS has more moving parts to operate yourself — CSI
drivers, load balancer controllers, and RBAC are all things ECS handles invisibly.

## Component Decisions

### Managed node group (not self-managed, not Fargate)
AWS handles node provisioning, patching, and draining on upgrades. Self-managed nodes
would give more control (custom AMIs, kernel tuning) at the cost of owning that
lifecycle. Fargate would remove nodes entirely but doesn't support DaemonSets
(needed for aws-node/kube-proxy in some configs) and costs more per-pod at this scale.

### Postgres as a StatefulSet (not RDS)
Deliberately in-cluster for this project to learn StatefulSets, PVCs, and the EBS CSI
driver — concepts a managed database would hide. Tradeoffs accepted knowingly:
- Single replica, no automated backups, no Multi-AZ failover
- EBS volumes are AZ-locked — a node replacement in the wrong AZ leaves the pod
  `Pending` until manually rescheduled
- **In production, this would be RDS.** The app code doesn't care — `DATABASE_URL`
  is just a connection string either way.

### Database creation via initContainers (not an init script or migration tool)
Postgres's built-in `docker-entrypoint-initdb.d` only runs when the data directory is
completely empty on first boot — it silently skips on any restart with existing data,
which caused real outages during this build (see INTERVIEW-NOTES.md). initContainers
on the users/items Deployments run an idempotent `CREATE DATABASE IF NOT EXISTS`
equivalent every time those pods start, decoupled from Postgres's own lifecycle.

### IRSA for every controller (EBS CSI driver, LB controller), not node-role permissions
Each controller pod gets a narrowly-scoped IAM role bound to its own Kubernetes
ServiceAccount via OIDC federation. The alternative — granting these permissions to
the shared node IAM role — would let *any* pod on *any* node call `CreateVolume` or
`CreateLoadBalancer`. IRSA keeps blast radius to exactly the pod that needs it.

### GitHub Actions access via EKS Access Entries (not a broad aws-auth mapping)
The CI role is scoped to `AmazonEKSEditPolicy` on the `eks-helm` namespace only — not
cluster-admin. A leaked CI credential can redeploy or break the app, but cannot touch
`kube-system`, other namespaces, or cluster RBAC.

### Terraform plan/apply as separate CI jobs with a manual approval gate
`terraform plan` always exits 0 whether it shows zero changes or a full teardown —
so a naive one-step pipeline (plan then blind `apply -auto-approve`) can silently
apply a destructive change. This pipeline uses `-detailed-exitcode` to distinguish
"no changes" / "changes present" / "error", uploads the plan as an artifact, and
requires a human to click Approve (via a GitHub `production` Environment with
required reviewers) before that exact plan is applied.

### One NAT Gateway (not one per AZ)
Saves ~$32/month. Tradeoff: if the AZ hosting the NAT goes down, nodes in the other
AZ lose outbound internet (can't pull new images from ECR, though already-running
pods keep working). Acceptable for a portfolio project; a real production account
would use one NAT per AZ for full AZ independence.

## Networking Details

- VPC: `10.0.0.0/16`, 2 AZs, public (`10.0.1.0/24`, `10.0.2.0/24`) and private
  (`10.0.11.0/24`, `10.0.12.0/24`) subnets
- Public subnets tagged `kubernetes.io/role/elb=1` — required by the LB Controller
  to know where it can place internet-facing ALBs
- Private subnets tagged `kubernetes.io/role/internal-elb=1` and both subnet tiers
  tagged `kubernetes.io/cluster/eks-helm=shared` — required for EKS subnet discovery
- EKS API endpoint: both public and private access enabled (kubectl from a laptop,
  and nodes reaching the control plane from inside the VPC)

## CI/CD Pipeline

Four GitHub Actions workflows, each triggered by path filters so unrelated changes
don't cause unnecessary rebuilds:

- `deploy-api-gateway.yml`, `deploy-users.yml`, `deploy-items.yml` — build image,
  tag with git SHA, push to ECR, `helm upgrade --reuse-values --set <service>.image.tag=<sha> --wait`
- `deploy-infra.yml` — `plan` job runs on every push to `infra/**`; `apply` job
  requires manual approval via a GitHub Environment before touching AWS

Images are tagged with the git SHA, never `latest` — `kubectl describe pod` always
shows exactly which commit is running.

## Known Limitations (by design, for a portfolio project)

- No ArgoCD/GitOps — deploys happen via CI pushing directly with `helm upgrade`,
  not by a controller reconciling from a Git repo. That's Project 4.
- No autoscaling (HPA/Cluster Autoscaler) — fixed 2 replicas per service, 2 nodes.
- No observability stack (Prometheus/Grafana) — also Project 4.
- Single-replica Postgres with no backups — RDS would be the production answer.
