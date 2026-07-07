# ── EKS Access Entries for GitHub Actions ──────────────────────────────────────
# IAM alone doesn't grant Kubernetes API access — EKS requires a separate
# mapping from IAM identity to Kubernetes permissions. This used to require
# manually editing the aws-auth ConfigMap; AWS now exposes it as a native
# EKS API (Access Entries), which we can manage directly in Terraform
# without needing the Kubernetes provider or touching aws-auth by hand.
#
# Scope: AmazonEKSEditPolicy scoped to the eks-helm namespace only — not
# cluster-admin. A leaked CI credential can redeploy/break the app, but
# cannot touch kube-system, other namespaces, or cluster-wide RBAC.

resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_iam_role.github_actions.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_iam_role.github_actions.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["eks-helm"]
  }
}
