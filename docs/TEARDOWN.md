# Teardown Log

Destroy order to avoid dependency errors:

1. `helm uninstall eks-app -n eks-helm` — remove all Kubernetes resources
2. `terraform destroy` in `infra/` — removes EKS, node group, VPC, ECR, IAM
3. Verify in AWS Console: EKS clusters, EC2 instances, NAT Gateways, Load Balancers

## Sessions

<!-- Add dated entries here after each destroy -->
