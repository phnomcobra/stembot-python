#!/usr/bin/python3
from stembot.controller.mpi import MPI
from stembot.controller.control import Control

class Root(object):
    mpi = MPI()
    control = Control()
