#!/usr/bin/python3

from stembot.dao import Collection

def get(name, default=None):
    kvstore = Collection('kvstore')

    try:
        key = kvstore.find(name=name)[0]
    except:
        key = kvstore.get_object()
        key.object['name'] = name
        key.object['value'] = default
        key.set()

    try:
        return key.object['value']
    except:
        key.object['value'] = default
        key.set()
        return default

def set(name, value):
    kvstore = Collection('kvstore')

    try:
        key = kvstore.find(name=name)[0]
    except:
        key = kvstore.get_object()

    key.object['name'] = name
    key.object['value'] = value
    key.set()

def delete(name):
    try:
        key = Collection('kvstore').find(name=name)[0]
        key.destroy()
    except:
        pass

def get_all():
    pairs = {}

    for pair in Collection('kvstore').find():
        try:
            pairs[pair.object['name']] = pair.object['value']
        except:
            pair.destroy()

    return pairs

kvstore = Collection('kvstore')
kvstore.create_attribute('name', "/name")
