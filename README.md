# django-orders-service: CI/CD to GKE with Helm (push-based)

Flow
  PR:   lint + tests + scan source + helm lint/render + build + scan image   (no push, no deploy)
  main: same -> push image (tag = git SHA) -> deploy dev -> staging -> [approval] -> prod
        each deploy: helm upgrade --atomic -> smoke test -> auto-rollback if smoke fails

## Day plan (about 7 hours if nothing snags)
| Time | Step |
|---|---|
| 0:00-0:45 | Run locally: `SECRET_KEY=x python manage.py test`, build the image, run it with docker, curl /healthz and /orders |
| 0:45-1:30 | GCP setup: project, enable APIs, Artifact Registry, create Autopilot cluster |
| 1:30-2:30 | Workload Identity Federation + two service accounts + GitHub variables/environments |
| 2:30-3:30 | Push to a branch, open a PR: watch CI pass. Fix whatever breaks (this IS the learning) |
| 3:30-4:30 | Merge to main: watch image push and dev deploy. Verify with kubectl |
| 4:30-5:30 | Staging, prod approval, then break things on purpose (below) |
| 5:30-7:00 | Explain the whole thing out loud using INTERVIEW.md. Then destroy the cluster |

## 1. Run locally first
```bash
pip install -r requirements-dev.txt
SECRET_KEY=x python manage.py test
docker build -t orders:local .
docker run --rm -p 8080:8080 -e SECRET_KEY=x -e ALLOWED_HOSTS=localhost orders:local
curl localhost:8080/healthz ; curl localhost:8080/orders
```

## 2. GCP setup
```bash
export PROJECT_ID=your-project REGION=us-central1 REPO_GH=ORG/REPO
gcloud config set project $PROJECT_ID
gcloud services enable container.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com

gcloud artifacts repositories create orders --repository-format=docker --location=$REGION
gcloud container clusters create-auto orders-cluster --region=$REGION
```
One cluster with three namespaces (dev/staging/prod) keeps cost low. In real companies these are
separate clusters or projects; say so in the interview.

Service accounts and Workload Identity Federation:
```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud iam service-accounts create gha-ci
gcloud iam service-accounts create gha-deploy
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:gha-ci@$PROJECT_ID.iam.gserviceaccount.com --role=roles/artifactregistry.writer
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:gha-deploy@$PROJECT_ID.iam.gserviceaccount.com --role=roles/container.developer

gcloud iam workload-identity-pools create github-pool --location=global
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global --workload-identity-pool=github-pool \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$REPO_GH'"

for SA in gha-ci gha-deploy; do
  gcloud iam service-accounts add-iam-policy-binding $SA@$PROJECT_ID.iam.gserviceaccount.com \
    --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$REPO_GH"
done
```

## 3. Create the Django secret in each namespace (out-of-band, never in Git)
```bash
gcloud container clusters get-credentials orders-cluster --region=$REGION
for ns in dev staging prod; do
  kubectl create namespace $ns --dry-run=client -o yaml | kubectl apply -f -
  kubectl create secret generic orders-secret -n $ns \
    --from-literal=SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(50))')"
done
```

## 4. GitHub configuration
Repository variables: GCP_PROJECT_ID, GCP_REGION, AR_REPO=orders,
WIF_PROVIDER=projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider,
CI_SERVICE_ACCOUNT=gha-ci@PROJECT_ID.iam.gserviceaccount.com,
DEPLOY_SERVICE_ACCOUNT=gha-deploy@PROJECT_ID.iam.gserviceaccount.com

Environments dev, staging, prod: each gets GKE_CLUSTER=orders-cluster and GKE_LOCATION=us-central1.
Add Required reviewers on prod. Protect main (require PR + passing checks).

## 5. Verify a deploy
```bash
kubectl get pods -n dev
kubectl port-forward -n dev svc/orders-service 8080:80
curl localhost:8080/orders
helm history orders-service -n dev
```

## 6. Break things on purpose (this is what makes you interview-ready)
1. Remove `/ready` handling or set a wrong probe path: watch `--atomic` roll back. Read `kubectl describe pod`.
2. Delete the secret in dev and redeploy: see CreateContainerConfigError. Fix it.
3. Set a memory limit of 20Mi: see OOMKilled in `kubectl describe pod`.
4. Use a non-existent image tag: see ImagePullBackOff.
5. Remove the Host handling in middleware.py: see probes fail with 400. (The classic Django-on-Kubernetes bug.)
6. Make the smoke test fail: watch the automatic `helm rollback`.
7. Add a fake HIGH CVE dependency or a hardcoded fake secret: watch Trivy block the PR.

## 7. Cleanup (do not skip: protects your credits)
```bash
gcloud container clusters delete orders-cluster --region=$REGION
```
Remove the cluster after each session; recreate it next time (about 5-10 minutes).

## Known limitations (say them yourself in the interview)
- Push-based CD: CI holds cluster access, no drift detection, audit trail in pipeline logs. GitOps (Argo CD) fixes these.
- No database: production would use Cloud SQL (private IP or Auth Proxy) with Workload Identity.
- Secrets are created manually: production would use External Secrets Operator + Secret Manager.
- No Ingress/TLS: production would use Gateway API + managed certificates + WAF (Cloud Armor).
- No Cosign/Binary Authorization, no metrics-based canary, no centralized alerting.
- One cluster for all environments (cost); real setups isolate prod.
- Public GKE endpoint (so GitHub-hosted runners can reach it); real setups use a private cluster plus self-hosted runners or a DNS-based endpoint.
