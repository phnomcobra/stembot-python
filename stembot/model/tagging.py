#!/usr/bin/python3

import traceback

from stembot.dao.document import Collection

def get_tag_values():
    tags = Collection('tags')
    
    values = []
    for tag in tags.find():
        try:
            values.append(tag.object['value'])
        except:
            tag.destroy()
    
    return values

def set_tag_value(value):
    value = str(value)
    
    tags = Collection('tags')
    
    if value not in get_tag_values():
        tag = tags.get_object()
        tag.object['value'] = value
        tag.set()

def del_tag_value(value):
    for tag in tags.find(value=value):
        tag.destroy()

tags = Collection('tags')
tags.create_attribute('value', "['value']")