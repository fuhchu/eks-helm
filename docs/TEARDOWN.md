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

Cluster addons (EBS CSI driver, AWS Load Balancer Controller, External Secrets
Operator) are NOT installed by `terraform apply` alone — they're one-time Helm
installs / addon creations. Order matters: ESO + the ClusterSecretStore must exist
before `helm install eks-app`, or the ExternalSecret resources fail to sync and the
pods have no DB credentials.

1. `terraform apply` in `infra/` — recreates everything, including a NEW ACM
   cert (old one gone) → note the new `acm_validation_records` output, and a NEW
   generated Postgres password written to Secrets Manager (`eks-helm/postgres`).
   Note: the Secrets Manager secret uses `recovery_window_in_days = 0`, so the
   name is freed immediately on destroy and can be reused here without the usual
   7–30 day wait.
2. Add/update the ACM validation CNAME in Namecheap, wait for `ISSUED`
3. Re-push images to ECR (force_delete wipes the repos) — or just re-run the
   CI/CD workflows once code is pushed
4. Reinstall cluster addons:
   - EBS CSI driver: managed by Terraform (`aws_eks_addon`), already present
   - AWS Load Balancer Controller: `helm install aws-load-balancer-controller ...`
     (see Milestone 4 command, with `--set vpcId=<new vpc id>`)
   - External Secrets Operator: `helm install external-secrets ... --set
     serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=<external_secrets_role_arn>`
5. `kubectl apply -f manifests/cluster-secret-store.yaml` and confirm
   `kubectl get clustersecretstore aws-secrets-manager` shows STATUS `Valid`
6. `helm dependency build helm/eks-app/` then `helm install eks-app helm/eks-app/ -n eks-helm`
   (ESO materializes the DB credential Secrets; no password passed on the CLI)
7. Update the `eks-helm` CNAME in Namecheap to the new ALB DNS name

## Sessions

<!-- Add dated entries here after each destroy -->
