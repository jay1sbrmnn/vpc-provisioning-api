variable "aws_region" {
  description = "AWS Region used for the control plane and provisioned VPCs."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Short name used as the prefix for AWS resources."
  type        = string
  default     = "vpc-provisioning-api"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}
