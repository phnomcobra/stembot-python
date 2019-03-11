#!/usr/bin/python

from threading import Lock
from copy import deepcopy

counters_lock = Lock()
counters = {}

def increment(name, value = 1):
    counters_lock.acquire()
    
    if name not in counters:
        counters[name] = int(value)
    else:
        counters[name] += int(value)
       
    counters_lock.release()

def decrement(name, value = 1):
    counters_lock.acquire()
    
    if name not in counters:
        counters[name] = -1 * int(value)
    else:
        counters[name] -= int(value)
        
    counters_lock.release()

def set(name, value):
    counters_lock.acquire()
    
    counters[name] = int(value)
    
    counters_lock.release()

def get(name):
    counters_lock.acquire()
    
    if name not in counters:
        counters[name] = 0
    
    temp = counters[name]
    
    counters_lock.release()
    
    return temp

def get_all():
    counters_lock.acquire()
    
    temp = deepcopy(counters)
    
    counters_lock.release()

    return temp
