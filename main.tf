terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
    profile = "UCB-FederatedAdmins-557418946771"
    region = "us-east-2"
}

resource "aws_instance" "web" {
    ami = "ami-06e46074ae430fba6"
    instance_type = "t2.micro"

    tags = {
        Name = "Helloworld"
    }
  
}