
#import libs
from flask import *
import os
from werkzeug.utils import secure_filename
import subprocess
import logging
import boto3
from botocore.exceptions import ClientError
import pathlib
from flask_socketio import SocketIO, send
import uuid

app = Flask(__name__)
#key for the sockek : R S S are teammates
app.config['SECRET_KEY'] = 'RSS'
socketio = SocketIO(app)

UPLOAD_FOLDER = 'static/uploads'
#allow image formats
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

BUCKET_NAME = "ssk-input"


###Sqs env ###
client = boto3.resource('sqs', region_name='us-east-1',
                        aws_access_key_id="AKIA4ENLEYAATY6MO54E",
                        aws_secret_access_key="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")

print(client)

webToControllerQueue = client.get_queue_by_name(QueueName='webToControllerQueue.fifo')
controllerToWebQueue = client.get_queue_by_name(QueueName='controllerToWebQueue.fifo')

def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3')
    try:
	#upload file to s3
        response = s3_client.upload_file(file_name, bucket, object_name)
        url =  object_name
        print(url)
        ddId = str(uuid.uuid4())
	#tell controller that an image is ready for processing 
        responseOfSQS = webToControllerQueue.send_message(MessageBody=url,MessageGroupId="webtocontroller",MessageDeduplicationId=ddId)
        print(responseOfSQS)
        print(url)

    except ClientError as e:
        logging.error(e)
        return False
    return True


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return redirect('/submit')

@app.route('/output',methods=['POST'])
def outputOP():
    if request.method == "POST":
        print(request.form)
        singleOp = request.form['output']
        #return redirect('/submit')
        print(singleOp)
        socketio.emit('Outputevent', {'data': singleOp})
        return "Hello from output"

@app.route('/submit', methods=['POST', 'GET'])
def submit():
    if request.method == "POST":
        files = request.files.getlist("files")
        for file in files:
            if file and allowed_file(file.filename):
		#save the file locally and call send to s3
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file_posix_path = pathlib.Path(file_path)
                upload_file(str(file_posix_path.resolve()), BUCKET_NAME,
                            object_name=file_posix_path.name)
                # output = subprocess.check_call("cat {}".format(file_path))
        return 'Hi'
    return render_template('submit.html')


@socketio.on('message')
def handleMessage(msg):
    print('Message : ' + msg)
    send(msg, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, port=5000, host="0.0.0.0")
    #app.run(port=5000, debug=True)

