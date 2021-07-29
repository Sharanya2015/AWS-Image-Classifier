#init and import libs
import boto3
import requests
import time

client = boto3.resource('sqs', region_name='us-east-1',
                    aws_access_key_id="AKIA4ENLEYAATY6MO54E",
                    aws_secret_access_key="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")

controllerToWebQueue = client.get_queue_by_name(QueueName='controllerToWebQueue.fifo')

URL = "http://localhost:5000/output"
isMessageReceived=False
#if a message is recieved in the loop do not wait in the loop for receiving new message
while True:
    for message in controllerToWebQueue.receive_messages():
        isMessageReceived = True
        print("Received message from controller inside SQS Listner as output" + message.body)
        PARAMS = {'output' : message.body}
	#post on output url of sqs server
        r = requests.post(url = URL, data = PARAMS)
        message.delete()
        #print(r.json())
    if(not isMessageReceived):
        #print("No Message in output sleeping for sometime")
        time.sleep(0.5)
    else:
        isMessageReceived = False
