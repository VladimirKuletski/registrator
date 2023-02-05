#!/bin/bash
aws cloudformation deploy --template ./aws_single_instance_hosting.yaml --stack-name registrator --profile personal --region us-east-1 --parameter-overrides InstanceType=t3.small KeyName=store LatestAmiId=/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2 SSHLocation=0.0.0.0/0 --capabilities CAPABILITY_IAM
