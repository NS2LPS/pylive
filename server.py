import zmq
import time
from pydata import Data
import msgpack
import msgpack_numpy as m
import numpy as np
m.patch()


# Create ZMQ socket
port = "5556"
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:%s" % port)

def send_data(socket, data, topic='data', flags=0, copy=True, track=False):
    """send a data object"""
    data_array = data.__data__
    md = dict(
        attrs = data.__attributes__,
        data_attrs = data.__data_attributes__
    )
    socket.send(topic.encode(), flags|zmq.SNDMORE)
    socket.send_json(md, flags|zmq.SNDMORE)
    return socket.send(msgpack.packb(data_array), flags, copy=copy, track=track)

while True:
    d = Data(x=np.arange(1000),y=np.random.randn(1000),z=2)
    send_data(socket, d)
    time.sleep(0.1)
