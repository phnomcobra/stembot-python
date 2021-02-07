#!/usr/bin/python3

import cherrypy

from stembot.controller.mpi import MPI

class Root(object):
    mpi = MPI()
