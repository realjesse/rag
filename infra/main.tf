terraform {
  required_version = ">= 1.10, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  profile = "terraform-dev"

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
    }
  }
}

# ---------- Settings ----------

variable "aws_region" {
  description = "AWS Region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short lowercase name used in resource names."
  type        = string
  default     = "rag-dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,29}$", var.project_name))
    error_message = "Use 1-30 lowercase letters, digits, or hyphens, starting with a letter."
  }
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version; check support before applying."
  type        = string
  default     = "1.35"
}

variable "admin_principal_arn" {
  description = "Existing IAM role/user ARN for kubectl access. For SSO use the IAM role ARN, not an STS assumed-role session ARN."
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:(role|user)/.+$", var.admin_principal_arn))
    error_message = "Supply an existing IAM role or IAM user ARN (not an STS session ARN or account root ARN)."
  }
}

variable "api_allowed_cidrs" {
  description = "Public IPv4 CIDRs allowed to reach the Kubernetes API, typically your public IP followed by /32. Update if your IP changes."
  type        = list(string)

  validation {
    condition     = length(var.api_allowed_cidrs) > 0 && alltrue([for cidr in var.api_allowed_cidrs : can(cidrnetmask(cidr))])
    error_message = "Supply at least one valid IPv4 CIDR."
  }
}

data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

# ---------- Networking: two public subnets, no NAT gateway ----------

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.project_name }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                     = "${var.project_name}-public-${count.index + 1}"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ---------- Container registry ----------

resource "aws_ecr_repository" "api" {
  name                 = var.project_name
  image_tag_mutability = "IMMUTABLE"

  # Development convenience: terraform destroy also removes stored images.
  # Use false if images must be protected from deletion.
  force_delete = true
}

# ---------- AWS permissions for EKS and its EC2 worker ----------

resource "aws_iam_role" "cluster" {
  name = "${var.project_name}-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "node" {
  name = "${var.project_name}-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly",
    # Start with the CNI policy on the node role; move it to a dedicated
    # workload identity when refining permissions later.
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
  ])
  role       = aws_iam_role.node.name
  policy_arn = each.value
}

# ---------- Kubernetes control plane and one EC2 worker ----------

resource "aws_eks_cluster" "main" {
  name     = var.project_name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  # Install the default CNI, kube-proxy, and CoreDNS add-ons.
  bootstrap_self_managed_addons = true

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }

  vpc_config {
    subnet_ids              = aws_subnet.public[*].id
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.api_allowed_cidrs
  }

  depends_on = [aws_iam_role_policy_attachment.cluster]
}

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-worker"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.public[*].id
  version         = var.kubernetes_version
  ami_type        = "AL2023_x86_64_STANDARD"
  instance_types  = ["t3.medium"]
  capacity_type   = "ON_DEMAND"
  disk_size       = 20

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 2
  }

  depends_on = [
    aws_iam_role_policy_attachment.node,
    aws_route_table_association.public,
  ]
}

# The chosen existing identity gets development-cluster administration.
# A separate, narrower role for GitHub Actions can be added later.
resource "aws_eks_access_entry" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = var.admin_principal_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_eks_access_entry.admin.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

# ---------- Values needed by the next deployment step ----------

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "configure_kubectl" {
  description = "Run while authenticated as admin_principal_arn (with eks:DescribeCluster permission)."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.main.name}"
}