#!/usr/bin/python

import cherrypy

from httpsmpi import MPI

class Root(object):
    mpi = MPI()
