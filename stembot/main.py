#!/usr/bin/python3
################################################################################
# MAIN
#
# Justin Dierking
# justin.l.dierking.civ@mail.mil
# (614) 692 2050
#
# 07/18/2017 Original construction
# 01/26/2021 Port to Python3
################################################################################

import cherrypy
import hashlib

from base64 import b64encode        
from stembot.model import kvstore
from stembot.dao.utils import sucky_uuid
from stembot.controller.root import Root

def start():
    config = {
        'agtuuid': kvstore.get(name='agtuuid', default=sucky_uuid()),
        'log.screen': False,
        'server.socket_host': kvstore.get(name='socket_host', default='0.0.0.0'),
        'server.socket_port': kvstore.get(name='socket_port', default=53080),
        'server.secret_digest': kvstore.get(
            name='secret_digest',
            default=b64encode(hashlib.sha256('changeme'.encode()).digest()).decode()
        ),
        'request.show_tracebacks': False,
        'request.show_mismatched_params': False
    }
    
    cherrypy.config.update(config)
            
    cherrypy.quickstart(Root())
