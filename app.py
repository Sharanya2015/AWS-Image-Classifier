#each individual instance on its inseption looks at the queue
#reads the message
#message becomes unavailable from queue for certain amount of time
#there is a threadshold till which message is blocked for reading again in SQS settings.
#once the message is processed completely and response is sent back to controller,
#app tier waits for certain amount of time to expect a new image to process from controller
#If it does not recieve any new image it terminates itself after sending a message to controller

### ENV SETUP
import boto3
import subprocess
import time
import uuid

###ENV SETUP
client = boto3.resource('sqs', region_name='us-east-1',
                    aws_access_key_id="AKIA4ENLEYAATY6MO54E", 
                    aws_secret_access_key="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")
                    
print(client)

s3 = boto3.client('s3',region_name='us-east-1',
                    aws_access_key_id="AKIA4ENLEYAATY6MO54E",
                    aws_secret_access_key="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")
controllerToAppQueueUrl = ""

controllerToAppQueue = client.get_queue_by_name(QueueName='controllerToAppQueue.fifo')
appToControllerQueue = client.get_queue_by_name(QueueName='appToControllerQueue.fifo')

###################
#APP LOGIC
isImageProcessed = False
shouldExit = 0

instanceIDValue = ""
originalURL= ""
getInstanceShOp = subprocess.getstatusoutput(f'sh getInstanceID.sh')
instanceIDValue = getInstanceShOp[1]
while True:
    print('_____Looping')
    #Read a message from controller
    for message in controllerToAppQueue.receive_messages():
        # Print out the body of the message
        print('Received this URL to process {0}'.format(message.body))
        url = message.body
        originalURL=url
	#Create a deduplication id for the message
        ddId =str(uuid.uuid4())
	#Tell controller that this instance has started processing the request and is not free to accept new request
        appToControllerQueue.send_message(MessageBody=url,
        MessageAttributes={
        'status': {
            'DataType': 'String',
            'StringValue': 'PROCESSING'
        },
        'instanceid': {
            'DataType': 'String',
            'StringValue': instanceIDValue
        }
        },
        MessageGroupId = "apptocontroller",MessageDeduplicationId=ddId)
        #download the url to local storage
        s3.download_file('ssk-input',url,url)
        print('Downloaded file successfully')
	#call model provided by prof and get the return using system command
        s = subprocess.getstatusoutput(f'python3 image_classification.py ' + url)
        #s = subprocess.getstatusoutput(f''+professor_command + inputfilepath)
        print(s)
        isImageProcessed = True
        outputRSS = url + ',' + s[1]
	#create a deduplication ID For the message that tells controller that it has completed processing
        ddID_forCompleted = str(uuid.uuid4())
        appToControllerQueue.send_message(MessageBody=outputRSS,
        MessageAttributes={
        'status': {
            'DataType': 'String',
            'StringValue': 'COMPLETED'
        },
        'instanceid': {
            'DataType': 'String',
            'StringValue': instanceIDValue
        }
        },
        MessageGroupId = "apptocontroller",MessageDeduplicationId=ddID_forCompleted)        
        print("Check apptocontrollerqueur")
        message.delete()
        #create a message and send to controller that a job is done
        #job here is done



    if(shouldExit>35): #waiting for 35 seconds to exit the instance
        print('Breaking from the while loop')
        break
    if(isImageProcessed == False):
	#if no image was processed in the read sqs queue loop,
	#wait for 1 second in the hopes that new message appears in the queue
        print('Looping again')
        shouldExit = shouldExit+1
        time.sleep(1)
    else:
        print('setting isImageProcessed to false')
	#if an image was processed in this loop, reset every counter and start a new loop
        shouldExit = 0
        isImageProcessed = False

print("Notifying controller that instance is getting destroyed")


ddID_forDestroy = str(uuid.uuid4())
appToControllerQueue.send_message(MessageBody="BYE",
        MessageAttributes={
        'status': {
            'DataType': 'String',
            'StringValue': 'DESTROY'
        },
        'instanceid': {
            'DataType': 'String',
            'StringValue': instanceIDValue
        }
        },
        MessageGroupId = "apptocontroller",MessageDeduplicationId=ddID_forDestroy)        
print("Check apptocontrollerqueur")
print("Exiting instance")

#make sure that the script is executable
terminationCommand = "sh terminateInstance.sh " + instanceIDValue
s = subprocess.getstatusoutput(terminationCommand)
print(s)
#self kill code
