#!/bin/bash

EC2_INSTANCE_ID=$(ec2metadata --instance-id)
echo $EC2_INSTANCE_ID

