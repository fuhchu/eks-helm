# Teardown Log

Destroy order to avoid dependency errors:

1. `helm uninstall eks-app -n eks-helm` — removes app pods, Services, Ingress
   (this deletes the ALB — wait ~1 min for AWS to actually remove it before
   the next step, or `terraform destroy` can fail trying to delete subnets
   still referenced by a lingering ALB)
2. `kubectl delete pvc data-postgres-0 -n eks-helm` — deletes the EBS volume
   (not automatically removed by `helm uninstall`)
3. `terraform destroy` in `infra/` — removes EKS, node group, VPC, NAT, ECR,
   IAM roles, ACM cert, EKS addons, Access Entries
4. Verify in AWS Console: EKS clusters, EC2 instances, NAT Gateways, Load
   Balancers, EBS volumes — confirm all gone
5. Namecheap DNS records (ACM validation CNAME, `eks-helm` CNAME) can stay —
   they just won't resolve to anything until the next `terraform apply`
   recreates the ALB, at which point update the `eks-helm` CNAME value again

## Recreating after a full teardown

1. `terraform apply` in `infra/` — recreates everything, including a NEW ACM
   cert (old one gone) → note the new `acm_validation_records` output
2. Add/update the ACM validation CNAME in Namecheap, wait for `ISSUED`
3. Re-push images to ECR (force_delete wipes the repos) — or just re-run the
   CI/CD workflows once code is pushed
4. `helm dependency build helm/eks-app/` then `helm install eks-app helm/eks-app/ -n eks-helm`
5. Update the `eks-helm` CNAME in Namecheap to the new ALB DNS name

## Sessions

<!-- Add dated entries here after each destroy -->
