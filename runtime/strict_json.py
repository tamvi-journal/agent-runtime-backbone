"""Reject ambiguous or nonstandard JSON at trust boundaries."""
import json

def _pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise ValueError("duplicate_json_key")
        out[k]=v
    return out

def _constant(_):
    raise ValueError("invalid_json_constant")

def loads(data):
    return json.loads(data,object_pairs_hook=_pairs,parse_constant=_constant)
