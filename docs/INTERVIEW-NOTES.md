# Interview Notes

Real incidents hit while building this project, framed as answers to
"tell me about a time you debugged a production issue."

---

## "PVC stuck Pending forever"

**Symptom:** `kubectl get pvc` showed `data-postgres-0` stuck in `Pending` indefinitely.

**Root cause:** EKS 1.23+ removed the in-tree EBS volume provisioner from Kubernetes
itself. It's now a separate addon (`aws-ebs-csi-driver`) that must be explicitly
installed — the `gp2` StorageClass still exists and references it, but nothing
was listening to fulfill the request.

**How I found it:** `kubectl describe pvc` showed the event
`Waiting for a volume to be created either by the external provisioner
'ebs.csi.aws.com' or manually by the system administrator` — named the exact
provisioner that was missing.

**Fix:** `aws eks create-addon --addon-name aws-ebs-csi-driver`, then added it to
Terraform (`aws_eks_addon` resource) so future clusters have it from day one.

**What I'd say in an interview:** "Always check `Pending` before `CrashLoopBackOff`
— a crashing app pod is often several layers downstream of a missing cluster
capability. I traced app crash → DB unreachable → DB pod pending → PVC pending →
missing CSI driver, four layers deep."

---

## "The CSI driver installed but kept crashing"

**Symptom:** Addon installed, but `ebs-csi-controller` pods were in
`CrashLoopBackOff` and the addon itself stayed in `CREATING` for 30+ minutes.

**Root cause:** The controller pod had no AWS credentials. `kubectl logs` showed
`no EC2 IMDS role found` — it tried to fall back to the node's instance profile
and found nothing, because the node role has no EC2 volume permissions (by design
— see IRSA note below).

**Fix:** Created an IRSA role (`aws_iam_role` with a trust policy scoped to the
`ebs-csi-controller-sa` ServiceAccount in `kube-system`) and attached
`AmazonEBSCSIDriverPolicy`. Had to delete the stuck addon and recreate it with
`service_account_role_arn` set from the start — AWS won't let you update an addon
stuck in `CREATING`.

**What I'd say in an interview:** "This is why I use IRSA instead of putting
permissions on the node role — every controller gets exactly the AWS permissions
it needs, scoped to its own ServiceAccount via OIDC federation, so a compromised
pod can't call APIs outside its job."

---

## "Postgres wouldn't initialize on a fresh EBS volume"

**Symptom:** `postgres-0` logs showed:
`initdb: error: directory "/var/lib/postgresql/data" exists but is not empty`
`It contains a lost+found directory`

**Root cause:** ext4 filesystems (which EBS uses) create a `lost+found` directory
at the root of every new volume for filesystem-recovery purposes. Postgres's
`initdb` refuses to initialize in any non-empty directory as a data-safety measure
— it can't tell the difference between "harmless lost+found" and "there might
already be a real database here, don't overwrite it."

**Fix:** Set `PGDATA=/var/lib/postgresql/data/pgdata` so Postgres initializes in
a clean subdirectory instead of the volume root.

**What I'd say in an interview:** "This is a well-known gotcha with any database
container mounted directly onto an EBS/EFS volume — official production Helm
charts like Bitnami's set PGDATA to a subdirectory for exactly this reason."

---

## "Databases disappeared after a pod restart"

**Symptom:** App worked, then started throwing `database "usersdb" does not exist`
after Postgres restarted.

**Root cause:** I'd initially relied on Postgres's `docker-entrypoint-initdb.d`
init scripts, which **only run when the data directory is completely empty on
first boot.** Several early crash-loop attempts had partially written to the
volume before failing, so on the next boot Postgres saw existing files, assumed
it was already initialized, and silently skipped running the init scripts —
without ever actually creating the databases.

**Fix:** Replaced the init-script approach with **initContainers** on the users
and items Deployments. Each runs an idempotent `SELECT ... FROM pg_database ||
CREATE DATABASE` check on every pod start — independent of Postgres's own
init lifecycle, safe to run repeatedly, self-healing on any restart.

**What I'd say in an interview:** "I initially used the database image's own init
mechanism, but it's tied to a specific lifecycle moment (first boot on an empty
volume) that doesn't hold up under real failure conditions like crash loops.
Moving the responsibility to an idempotent initContainer on the *consuming*
service made it self-healing regardless of what state Postgres was in."

---

## "Adding an unrelated feature almost destroyed the whole cluster"

**Symptom:** Ran `terraform apply` to add EKS Access Entries (for CI/CD RBAC) and
the plan showed `aws_eks_cluster.main must be replaced` — a full destroy and
recreate of the production cluster, for a change that should have been
purely additive.

**Root cause:** Adding an `access_config` block to enable the new Access Entry
authentication mode introduced a new attribute,
`bootstrap_cluster_creator_admin_permissions`, that I left unset. Terraform
treats this attribute as immutable once a cluster exists; leaving it unset
defaulted it to a *different* value than the cluster's actual current state
(`true`, set implicitly at creation), which the AWS provider interpreted as
a value change requiring full replacement.

**What actually saved this:** AWS itself refused the destroy —
`ResourceInUseException: Cluster has nodegroups attached` — so the apply failed
partway through instead of completing. The cluster survived because of that
safety check, not because I caught the problem in the plan review.

**Fix:** Explicitly set `bootstrap_cluster_creator_admin_permissions = true` in
the `access_config` block to match the cluster's actual existing state, which
turned the diff into `update in-place`.

**What I'd say in an interview:** "This is exactly why I review every `-/+`
line in a `terraform plan` before approving — a diff that looks like an
unrelated, additive change (enabling a new auth mode) triggered a resource
replacement because of one unset attribute with an implicit default. It's also
why I treat `apply` as a separate, gated step from `plan` in CI/CD — a
human needs to actually read the blast radius before approving it, not just
see a green checkmark."

---

## "terraform plan always shows green — how do you know CI actually caught a problem?"

**The realization:** `terraform plan` exits code `0` whether it detects zero
changes or a full-account teardown. A naive CI pipeline that runs `plan` then
`apply -auto-approve` will show green right up until the moment it deletes
production.

**Fix:** Used `terraform plan -detailed-exitcode`, which returns `0` (no changes),
`2` (changes present), or `1` (error) — then split the pipeline into a `plan` job
and a separate `apply` job gated behind a GitHub Environment with required
reviewers, so the exact reviewed plan artifact is what gets applied, not a
fresh plan that could differ from what was approved (a TOCTOU-style bug in
naive pipelines).

**What I'd say in an interview:** "This mirrors what Terraform Cloud, Atlantis,
and Spacelift all do natively — plan and apply are separate approval gates,
never a single auto-approved step, for anything touching shared infrastructure."
