import errno
from time import sleep

import os
from flasgger import Swagger
from flasgger.utils import swag_from
from flask import Flask, request
from nameko.standalone.rpc import ClusterRpcProxy

from src.layer import STATUS_FILES_DIRECTORY

app = Flask(__name__)
Swagger(app)

CONFIG = {'AMQP_URI': "pyamqp://guest:guest@localhost"}

TIMEOUT = 0.5
TIMEOUTS_NUMBER = 6


@app.route('/send', methods=['POST'])
@swag_from('docs/send.yml')
def send():
    logger = app.logger
    type = request.json.get('type')
    body = request.json.get('body')
    address = request.json.get('address')
    logger.info('Get message: %s,%s,%s' % (type, body, address))

    if not os.path.exists(os.path.dirname(STATUS_FILES_DIRECTORY)):
        try:
            os.makedirs(os.path.dirname(STATUS_FILES_DIRECTORY))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

    status_filename = STATUS_FILES_DIRECTORY + 'lock'
    status = None
    try:
        with open(status_filename, 'w+') as file:
            file.seek(0)
            file.write('sending')
            file.truncate()

        with ClusterRpcProxy(CONFIG) as rpc:
            # asynchronously spawning and email notification
            rpc.yowsup.send(type, body, address)

        # trying to wait for success or fail
        timeouts = 0
        while status is None and timeouts < TIMEOUTS_NUMBER:
            timeouts += 1
            try:
                with open(status_filename, 'r') as file:
                    text = file.read()
                    if text == 'success':
                        status = 'success'

                if status is None:
                    sleep(TIMEOUT)
            except:
                pass
    except:
        pass
    finally:
        try:
            os.remove(status_filename)
        except:
            pass

    if status == 'success':
        msg = "The message was successfully sent"
    elif status is None:
        msg = '{from: "", to:"", status: "undelivered"}'

    return msg, 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80)

