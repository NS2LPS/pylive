import json
import base64
import zmq
import numpy as np
import time 
import msgpack
import msgpack_numpy as m
m.patch()

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table
import threading


def create_zmq_socket(zmq_port="5556", topicfilter="data"):
    """ Create a ZMQ SUBSCRIBE socket """
    context = zmq.Context()
    zmq_socket = context.socket(zmq.SUB)
    zmq_socket.connect ("tcp://localhost:%s" % zmq_port)
    zmq_socket.setsockopt_string(zmq.SUBSCRIBE, topicfilter)
    return zmq_socket

def recv_data(flags=0, copy=True, track=False):
    """recv a data object"""
    with create_zmq_socket() as socket:
        topic = socket.recv(flags=flags, copy=copy, track=track)
        fields = socket.recv_json(flags=flags)
        values = socket.recv(flags=flags, copy=copy, track=track)
        return fields, values

lastdata = None
socket_lock = threading.Lock()
 
class Receiver(threading.Thread):
    def run(self):
        global lastdata
        while True:
            try:
                with create_zmq_socket() as socket:
                    while True:
                        msg = socket.recv_multipart()
                        socket_lock.acquire()
                        lastdata = (msg[1], msg[2],time.time())
                        socket_lock.release()
            except:
                pass
                             

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div(children=[
    html.H1(children='Live plot'),
    html.Div([
    html.Label('Update'),
    dcc.RadioItems(
        id = 'auto-update',
        options=[
            {'label': 'On', 'value': 'on'},
            {'label': 'Off', 'value': 'off'},
        ],
        value='on',
        labelStyle={'display': 'inline-block'}
    ),
    html.Label('Autoscale on update'),
    dcc.RadioItems(
        id = 'auto-scale',
        options=[
            {'label': 'On', 'value': 'on'},
            {'label': 'Off', 'value': 'off'},
        ],
        value='on',
        labelStyle={'display': 'inline-block'}
    ),
    ],style={'columnCount': 2}),  
    dcc.Interval(
        id='interval-component',
        interval=1000, # in milliseconds
        n_intervals=0
    ),
    html.Div([
    html.Label('X variable'),
    dcc.Dropdown(
        id='dropdown-x',
        multi=False
    ),
    html.Label('Y variable'),
    dcc.Dropdown(
        id='dropdown-y',
        multi=False
    ),
    ], style={'columnCount': 2}),
    dcc.Graph(id="main-graph"),
    dcc.Store(id='data-fields',data=None),
    dcc.Store(id='data-values',data=None),
    dcc.Store(id='data-time',data=None),
    dcc.Store(id='timer',data=time.time()),
    dash_table.DataTable(id='table'),
])


@app.callback(
    Output('interval-component', 'disabled'),
    Input('auto-update', 'value'))
def update_interval(val):
    return val!='on'

@app.callback(
    Output('data-fields', 'data'),
    Output('data-values', 'data'),
    Output('data-time', 'data'),
    Input('interval-component', 'n_intervals'),
    State('data-time', 'data'),
    State('auto-update', 'value'))
def update(n, prev_time_tag, auto_update):
    global lastdata
    socket_lock.acquire()
    if lastdata is not None and auto_update:
        time_tag = lastdata[2]
        if time_tag!=prev_time_tag:
            fields = lastdata[0].decode()
            values = base64.b64encode(lastdata[1]).decode()
        else:
            fields = dash.no_update
            values = dash.no_update
            time_tag = dash.no_update
    else:
        fields= dash.no_update
        values = dash.no_update
        time_tag = dash.no_update
    socket_lock.release()
    return fields, values, time_tag
            
@app.callback(Output('dropdown-x','options'),
              Output('dropdown-y','options'),
              Output('dropdown-x','value'), 
              Output('dropdown-y','value'),
              Output('auto-scale','value'),
              Input('data-fields','data'),
              State('dropdown-x', 'value'),
              State('dropdown-y', 'value'),
              State('auto-scale','value')
              )
def update_vars(fields, prev_x, prev_y, autoscale):
    if fields is None:
        return [], [], None, None, 'on'
    fields = json.loads(fields)
    options = [{'label': x, 'value': x} for x in fields['data_attrs']]
    new_options = [o['value'] for o in options]
    value_x = prev_x if prev_x in new_options else None
    value_y = prev_y if prev_y in new_options else None
    if autoscale=='off':
        autoscale = 'off' if value_x==prev_x and value_y==prev_y else 'on'
    return options, options, value_x, value_y, autoscale

@app.callback(Output('main-graph','figure'),
              Output('timer','data'),  
              Input('dropdown-x', 'value'),
              Input('dropdown-y', 'value'),
              State('data-values','data'),
              State('auto-scale','value'),
              State('timer','data'),
              )
def update_fig(x, y, values, autoscale, t):
    if y is None:
        return {'data':[{'x': [], 'y': [], 'type': 'line'}] , 'layout' : {'xaxis' : {'title': ''}, 'yaxis' : { 'title':  ''}}}, time.time()
    data = msgpack.unpackb(base64.b64decode(values))
    t = t if autoscale=='off' else time.time()
    if x is None:
        ret =  {'data': [{'x': np.arange(len(data[y])), 'y': data[y], 'type': 'line'}] , 'layout' : {'uirevision': t, 'yaxis' : { 'title':  y}}}
    else:
        ret = {'data': [{'x': data[x], 'y': data[y], 'type': 'line'}] , 'layout' : {'uirevision': t, 'xaxis' : {'title': x}, 'yaxis' : { 'title':  y}}}
    return ret, t

@app.callback(Output('table','columns'),
              Output('table','data'),
              Input('data-fields', 'data'),
              )
def update_table(fields):
    if fields is None:
        return [], []
    fields = json.loads(fields)
    attrs = fields['attrs']
    return [ {'name':c,'id':c} for c in attrs.keys()], [attrs]
    

if __name__ == '__main__':
    receiver_thread = Receiver()
    receiver_thread.start()
    app.run_server(debug=False, host='0.0.0.0', port=5013)
