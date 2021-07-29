#!/bin/bash
#use system commands to get instane id value 
EC2_INSTANCE_ID=$(ec2metadata --instance-id)
echo $EC2_INSTANCE_ID
