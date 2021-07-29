#!/bin/bash
#use system commands to kill the instance
#it accepts instance name as input which is provided using the getInstanceName script
ec2kill --aws-access-key AKIA4ENLEYAATY6MO54E  --aws-secret-key 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 $1
#echo $1
