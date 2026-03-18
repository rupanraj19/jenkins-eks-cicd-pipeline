# Jenkins CI/CD Pipeline with AWS EKS

A production-style CI/CD pipeline that automatically builds, pushes, and deploys a containerized Python Flask application to AWS EKS using Jenkins, Docker, Terraform, and CloudFormation.

---

## Architecture

```
GitHub Push → Jenkins (EC2) → Docker Build → Amazon ECR → Deploy to EKS
```

```
┌─────────────┐     Webhook      ┌─────────────────┐
│   GitHub    │ ──────────────▶  │  Jenkins (EC2)  │
│    Repo     │                  │   t2.micro       │
└─────────────┘                  └────────┬────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                   Docker Build     Push to ECR     Deploy to EKS
                          │               │               │
                          └───────────────┴───────────────┘
                                          │
                                 ┌────────▼────────┐
                                 │   AWS EKS       │
                                 │  (t3.small)     │
                                 │  Flask App      │
                                 └─────────────────┘
                                          │
                                 ┌────────▼────────┐
                                 │  LoadBalancer   │
                                 │  (Public URL)   │
                                 └─────────────────┘
```

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Jenkins | CI/CD pipeline automation |
| Docker | Containerize the Flask app |
| Amazon ECR | Private Docker image registry |
| Amazon EKS | Kubernetes cluster to run the app |
| Terraform | Provision VPC, EC2 (Jenkins), EKS cluster |
| CloudFormation | Provision ECR repository and IAM policies |
| GitHub Webhooks | Auto-trigger Jenkins on every push |
| Python Flask | Simple web application |

---

## Project Structure

```
jenkins-eks-cicd-pipeline/
├── app/
│   ├── app.py                  # Flask application
│   └── requirements.txt        # Python dependencies
├── k8s/
│   ├── deployment.yaml         # Kubernetes Deployment
│   └── service.yaml            # Kubernetes LoadBalancer Service
├── terraform/
│   ├── main.tf                 # VPC, EC2 (Jenkins), IAM, Security Groups
│   ├── eks.tf                  # EKS cluster and node group
│   ├── variables.tf            # Input variables
│   ├── outputs.tf              # Output values
│   └── versions.tf             # Provider version constraints
├── cloudformation/
│   └── ecr-iam.yaml            # ECR repository and IAM policies
├── Dockerfile                  # Container image definition
├── Jenkinsfile                 # Pipeline definition
└── .gitignore
```

---

## Pipeline Stages

```
Checkout → Build Docker Image → Push to ECR → Deploy to EKS
```

1. **Checkout** — Jenkins pulls the latest code from GitHub
2. **Build Docker Image** — Builds and tags the Flask app Docker image
3. **Push to ECR** — Authenticates with AWS and pushes the image to ECR
4. **Deploy to EKS** — Updates kubeconfig and applies Kubernetes manifests

---

## Infrastructure Setup

### Prerequisites
- AWS CLI configured locally
- Terraform installed
- kubectl installed
- An EC2 Key Pair in AWS

### Phase 1 — Terraform (VPC + EC2 + EKS)

```bash
cd terraform
terraform init
terraform apply -var="key_name=YOUR_KEY_PAIR_NAME"
```

Provisions:
- VPC with public and private subnets across 2 AZs
- NAT Gateway for private subnet internet access
- EC2 instance (t2.micro) with Jenkins, Docker, AWS CLI, kubectl auto-installed
- EKS cluster with 1x t3.small worker node
- IAM role for Jenkins EC2 with ECR and EKS permissions

### Phase 2 — CloudFormation (ECR + IAM)

```bash
cd cloudformation
aws cloudformation deploy \
  --template-file ecr-iam.yaml \
  --stack-name jenkins-ecr-iam \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

Provisions:
- ECR repository (`flask-cicd-app`)
- IAM managed policy for Jenkins to push images to ECR

### Phase 3 — EKS Access Configuration

```bash
# Grant your IAM user cluster admin access
aws eks create-access-entry \
  --cluster-name jenkins-cicd-cluster \
  --principal-arn arn:aws:iam::ACCOUNT_ID:user/YOUR_USER \
  --type STANDARD

aws eks associate-access-policy \
  --cluster-name jenkins-cicd-cluster \
  --principal-arn arn:aws:iam::ACCOUNT_ID:user/YOUR_USER \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster

# Grant Jenkins EC2 role cluster access
aws eks create-access-entry \
  --cluster-name jenkins-cicd-cluster \
  --principal-arn arn:aws:iam::ACCOUNT_ID:role/jenkins-ec2-role \
  --type STANDARD

aws eks associate-access-policy \
  --cluster-name jenkins-cicd-cluster \
  --principal-arn arn:aws:iam::ACCOUNT_ID:role/jenkins-ec2-role \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
```

### Phase 4 — Jenkins Configuration

```bash
# SSH into Jenkins EC2
ssh -i "your-key.pem" ubuntu@JENKINS_PUBLIC_IP

# Configure kubeconfig for Jenkins user
aws eks update-kubeconfig --name jenkins-cicd-cluster --region us-east-1
sudo mkdir -p /var/lib/jenkins/.kube
sudo cp ~/.kube/config /var/lib/jenkins/.kube/config
sudo chown -R jenkins:jenkins /var/lib/jenkins/.kube

# Verify
sudo -u jenkins kubectl get nodes
```

Jenkins Plugins required:
- Docker Pipeline
- Kubernetes CLI
- Amazon ECR
- AWS Credentials

---

## GitHub Webhook Setup

1. Go to GitHub repo → **Settings → Webhooks → Add webhook**
2. Payload URL: `http://JENKINS_IP:8080/github-webhook/`
3. Content type: `application/json`
4. Trigger: Push events only

In Jenkins job → **Configure → Build Triggers → Enable GitHub hook trigger for GITScm polling**

---

## Issues Encountered & Solutions

### 1. Jenkins GPG Key Signature Verification Failed
**Error:** `NO_PUBKEY 7198F4B714ABFC68` — Jenkins apt repo could not be verified.

**Solution:** The `.asc` key format wasn't compatible with apt. Had to convert to binary `.gpg` format using `gpg --dearmor`. Eventually resolved by downloading and installing Jenkins directly via `.deb` package from `mirrors.jenkins.io`.

---

### 2. Jenkins Version Too Old — Plugin Incompatibility
**Error:** `Failed to load: Docker Pipeline` — plugins required a newer version of Jenkins core.

**Solution:** Upgraded Jenkins from `2.479.3` to `2.541.2` by downloading the `.deb` directly:
```bash
wget https://mirrors.jenkins.io/debian-stable/jenkins_2.541.2_all.deb
sudo dpkg -i jenkins_2.541.2_all.deb
```

---

### 3. Terraform EKS Module — Unsupported Block Type
**Error:** `elastic_gpu_specifications` and `elastic_inference_accelerator` blocks not supported.

**Solution:** AWS provider version mismatch. Fixed by adding a `versions.tf` file pinning the AWS provider to `~> 5.0` and running `terraform init -upgrade`.

---

### 4. Ubuntu AMI Not Found
**Error:** `Your query returned no results` for the AMI data source.

**Solution:** AWS changed Ubuntu AMI naming format. Updated the filter from:
```
ubuntu/images/hvm-ssd/ubuntu-22.04-amd64-server-*
```
to:
```
ubuntu/images/hvm-ssd/ubuntu-*-22.04-amd64-server-*
```

---

### 5. Jenkins EC2 Missing EKS Permission
**Error:** `AccessDeniedException` — `jenkins-ec2-role` not authorized to perform `eks:DescribeCluster`.

**Solution:** Added an inline IAM policy to the Jenkins EC2 role in Terraform:
```hcl
resource "aws_iam_role_policy" "jenkins_eks_policy" {
  name = "jenkins-eks-access"
  role = aws_iam_role.jenkins_role.id
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = ["eks:DescribeCluster", "eks:ListClusters", "eks:AccessKubernetesApi"]
      Resource = "*"
    }]
  })
}
```

---

### 6. kubectl — Invalid API Version
**Error:** `exec plugin: invalid apiVersion "client.authentication.k8s.io/v1alpha1"`.

**Solution:** Old AWS CLI (v1.22) was generating outdated kubeconfig. Removed system-installed AWS CLI and installed AWS CLI v2:
```bash
sudo apt-get remove -y awscli
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install
sudo ln -sf /usr/local/bin/aws /usr/bin/aws
```

---

### 7. EKS Access — IAM User Not Authorized (aws-auth)
**Error:** `You must be logged in to the server` — IAM user `ruby` not in EKS access config.

**Solution:** Used the newer EKS Access Entries API instead of editing `aws-auth` ConfigMap manually:
```bash
aws eks create-access-entry --cluster-name jenkins-cicd-cluster \
  --principal-arn arn:aws:iam::ACCOUNT_ID:user/ruby --type STANDARD

aws eks associate-access-policy --cluster-name jenkins-cicd-cluster \
  --principal-arn arn:aws:iam::ACCOUNT_ID:user/ruby \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
```

---

### 8. Jenkins EC2 Cannot Reach EKS API Server
**Error:** `dial tcp 10.0.4.73:443: i/o timeout` — Jenkins EC2 in public subnet couldn't reach EKS API in private subnet.

**Solution:** Added a security group rule in Terraform to allow port 443 from Jenkins SG to EKS cluster SG:
```hcl
resource "aws_security_group_rule" "jenkins_to_eks" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.jenkins_sg.id
  security_group_id        = module.eks.cluster_security_group_id
}
```

---

### 9. Jenkins Docker Permission Denied
**Error:** `permission denied while trying to connect to the Docker daemon socket`.

**Solution:** Jenkins user was not in the docker group:
```bash
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
```

---

### 10. Large Terraform Provider Files Blocked by GitHub
**Error:** `File terraform-provider-aws_v6.36.0_x5.exe is 812.61 MB; exceeds GitHub's file size limit`.

**Solution:** `.terraform/` folder was accidentally committed. Removed from git history using `git filter-branch` and added `.gitignore`:
```
.terraform/
*.tfstate
*.tfstate.backup
.terraform.lock.hcl
*.pem
```

---

## Cost Estimate

| Resource | Type | Cost/day |
|---|---|---|
| EKS Control Plane | Managed | ~$2.40 |
| EKS Worker Node | t3.small x1 | ~$0.55 |
| Jenkins EC2 | t2.micro | ~$0.28 |
| NAT Gateway | - | ~$1.08 |
| **Total** | | **~$4.31/day** |

> ⚠️ Always run `terraform destroy` when not using the cluster to avoid unnecessary costs.

---

## Destroy Infrastructure

```bash
cd terraform
terraform destroy -var="key_name=YOUR_KEY_PAIR_NAME"

aws cloudformation delete-stack --stack-name jenkins-ecr-iam --region us-east-1
```
