#import libs
import boto3
import time
from datetime import datetime
import logging
from botocore.exceptions import ClientError
import uuid


###ENV SETUP
client = boto3.resource('sqs', region_name='us-east-1',
                    aws_access_key_id="AKIA4ENLEYAATY6MO54E", 
                    aws_secret_access_key="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")
                    
print(client)

webToControllerQueue = client.get_queue_by_name(QueueName='webToControllerQueue.fifo')
controllerToAppQueue = client.get_queue_by_name(QueueName='controllerToAppQueue.fifo')
appToControllerQueue = client.get_queue_by_name(QueueName='appToControllerQueue.fifo')
controllerToWebQueue = client.get_queue_by_name(QueueName='controllerToWebQueue.fifo')
uploadBucket = "ssk-output"
s3_upload_client = boto3.client('s3')
ec2 = boto3.resource('ec2', region_name='us-east-1')
print(ec2)
###Controller logic

# 
# Wait indefinitely for new messages
# Loop for a receiving a new message
# if a new message is received
# check if any already spawned instance is free for processing a new image
# if so do not spawn an instance, just send the message to already existing app instance
# if no instance is free for processing new image
# see If we are into the limit of instances which is 19
    # If we are in limit of instance limit 
    # spawn a new instance
    # publish the message and forget
    
#destination tracker
#Key: instanceID 
#Value can be   "MAY PROCESS" : Instance is free for processing a new request
#		"PROCESSING " : Instance is currently processing a image
#		"COMPLETED"   : Instance is done processing the image
#		"DESTROY"     : Instance is getting destroyed. after this message, key value pair is deleted from 
#				destinationTracker dictionary
instancesDict = {}

#this function checks if there is any already spawned instance free for processing a new request
def isAnyInstanceFree():
    print("_____Checking if there is any instance free for processing new image")
    for key in instancesDict:
        if (instancesDict[key] == "COMPLETED"):
	    #if instance has completed processing, mark it as it can process a new image
            instancesDict[key] = "MAY_PROCESS"
            print("This instance is free for processing : " + key)
            print("returning true from isAnyInstanceFree")
            return True

    print("DestinationsTracker Size :" + str(len(instancesDict)))
    print("No already spawned instance is free right now, wait")
    return False
    
#define max number of instances
MaxNumberOfInstances= 19
#this counter is a placeholder
CurrentNumberOfInstances=0

#a boolen to check if we recieved a message in the loop
#if a message is received we do not wait for the next message
#we start the next iternation of the loop immidiately
isAnyMessageReceived = False


#loop forever
while True:
    isAnyMessageReceived = False
	#check messages from app tier
    for message in appToControllerQueue.receive_messages(MessageAttributeNames=['status', 'instanceid']):
        isAnyMessageReceived = True 
        print('received message in appToControllerQueue {0}',format(message.body))
		#we are using message attributes to tell about the status of the app tier instance 
        if message.message_attributes is not None:
            print('message attribute is not None')
            actionType = message.message_attributes.get('status').get('StringValue')
            actionTypeText = '{0}'.format(actionType)
            print('Received actionType = ' + actionType )
            instancevalue = message.message_attributes.get('instanceid').get('StringValue')
            instance = '{0}'.format(instancevalue)
            print('Received instance = ' + instance)
			#ACTION TYPES HERE ARE SELF EXPLANATORY 
            if actionType == 'PROCESSING':
                now = datetime.now().time()
                instancesDict[instance] = "PROCESSING"
                print('This image has started processing: '+ message.body)
                print('Added to dict as processing')
            elif actionType == 'COMPLETED':
                print('This image has completed processing with Output: '+ message.body)
                instancesDict[instance] = "COMPLETED"
                print('Added to dict as completed')
                #This doesnt mean my instance is killed.
                #It means my instance is free to accept one more job for next 35 seconds
                result = message.body
                deduplication = str(uuid.uuid4())
				#Create a new output file to put in S3 bucket
                filenamePart = result.split(",")[0]
                file_name = filenamePart + ".txt"
                f = open(file_name, "w")
                f.write(result)
                f.close()
                try:
                    print("PUTTING DATA IN OUTPUT BUCKET")
                    object_name = file_name
                    response = s3_upload_client.upload_file(file_name, uploadBucket, object_name)
                except ClientError as e:
                    logging.error(e) 
				#sent the output to web tier
                controllerToWebQueue.send_message(MessageBody=result,MessageGroupId = "controllertoapp",MessageDeduplicationId=deduplication)
            elif actionType == "DESTROY":
                print('This AMI for image is being destroyed: '+ message.body)
                instancesDict[instance] = "DESTROY"
                #DELETE THIS IMAGEID from dict
                del instancesDict[instance] 
                CurrentNumberOfInstances = CurrentNumberOfInstances - 1
                print('Reduced current number of instances to : '+ str(CurrentNumberOfInstances))
                #instance will kill itself
			#delete the message from sqs queue
            message.delete()
        else:
            print("Message attributes are none")
			#execution wont come here
	#check if any already spawned instance is free for processing new image
    canAnyInstanceProcess = isAnyInstanceFree() 
    if( canAnyInstanceProcess or len(instancesDict) < MaxNumberOfInstances ):
        print("Can process at least one more image request and instanceDict size is" + str(len(instancesDict)))
		#read image from web to controller queue
        for message in webToControllerQueue.receive_messages():
            isAnyMessageReceived = True 
            # Print out the body of the message
            print("Received an image from web tier for processing")
            print('Received, {0}'.format(message.body))
            url = message.body
            ddId = str(uuid.uuid4())
            controllerToAppQueue.send_message(MessageBody=url,MessageGroupId = "controllertoapp",MessageDeduplicationId=ddId)
            print("Sent message to App tier for processing")
            #print('Deleting the message')
            #Let the queue know that the message is processed
            if(canAnyInstanceProcess):
                print("************SKIPPING INSTANCE CREATION*************")
            if(not canAnyInstanceProcess):
				#send user data to app tier instance to tell the app tier to start app tier script at it's inception
                user_data = '''#!/bin/bash
                cd /home/ubuntu/classifier
                echo $PWD > /tmp/test.txt
                which python3 > /tmp/py.txt
                nohup python3 app.py > /tmp/output.txt 2>&1'''
                instance_name = "APP_TIER_" + str(len(instancesDict)) 
				#launch an instance with instance name
                tagSpecification = {
                        'ResourceType' : 'instance',
                        'Tags' : [
                            { 
                                'Key' : 'Name',
                                'Value' : instance_name
                                },
                            ]
                        }
                instance = instances = ec2.create_instances(
                                    ImageId='ami-01c5cc5976c01a3b2',
                                    MinCount=1,
                                    MaxCount=1,
                                    InstanceType='t2.micro',
                                    KeyName='aws-kp-sb',
                                    SecurityGroupIds=['sg-0052fe3987d27001f'],
                                    UserData=user_data,
                                    TagSpecifications=[tagSpecification]
                )
                print("launched a new instance")
                instanceIDVal = instance[0].id
                #ec2.create_tags(Resources=[instanceIDVal], Tags=[{'Key': 'Name', 'Value': instance_name, }, ])
                instancesDict[instanceIDVal] = "LAUNCHED"
                print("Lenth of dict" + str(len(instancesDict)))
                CurrentNumberOfInstances = CurrentNumberOfInstances + 1
                print("Increased number of instances to " + str(CurrentNumberOfInstances))
            #I hope instance creation does not take that much time
            #if it does, we need to spawn a thread and not join to main thread
            #may be a callback works
            message.delete()
            print("deleted web to controller queue message")
            #send the URL message on controller to app queue
            #spawn instance
            #read new message
            #Already running MaxNumberOfInstances for processing
            #Can not read a new message
            #must sleep for 5 seconds and then again check if there are more instances available    

    if(not isAnyMessageReceived):
        time.sleep(2)

#code wont come here
print('Adios')
