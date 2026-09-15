#!/usr/bin/env python3
"""Explicit, single-operator file publication into the included debuggable checker.
No provider writes, installs, sockets, listener injection, or fleet scheduling.
"""
import argparse
import hashlib
import json
import math
import re
import shlex
import subprocess
import uuid
from pathlib import Path

TARGET='net.stakeout.duomove.checker'
REMOTE='files/duomove/fix.json'
FIELDS={'schema_version','generation','sequence','ttl_ms','lat','lon','accuracy','alt','altitude_datum','speed','bearing','vertical_accuracy'}

def validate(sample):
    if not isinstance(sample,dict) or sample.keys()-FIELDS:raise ValueError('unknown_field')
    def num(key,lo,hi,integer=False):
        x=sample.get(key)
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not lo<=x<=hi or (integer and x!=int(x)):
            raise ValueError('invalid_'+key)
        return x
    num('schema_version',1,1,True);num('generation',0,9_000_000_000_000_000,True)
    num('sequence',0,9_000_000_000_000_000,True);num('ttl_ms',100,30000,True)
    num('lat',-90,90);num('lon',-180,180);num('accuracy',0,100000)
    for k,lo,hi in [('alt',-12000,100000),('speed',0,400),('bearing',0,359.999999999),('vertical_accuracy',0,100000)]:
        if sample.get(k) is not None:num(k,lo,hi)
    if sample.get('alt') is not None:
        if sample.get('altitude_datum')!='WGS84_ELLIPSOID':raise ValueError('altitude_datum_required')
    elif sample.get('altitude_datum') is not None or sample.get('vertical_accuracy') is not None:
        raise ValueError('altitude_required')
    return dict(sample)

def publish(sample,serial,enabled=False,runner=subprocess.run):
    sample=validate(sample)
    if not isinstance(serial,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,254}',serial):
        raise ValueError('invalid_serial')
    if not enabled:return {'status':'validated_only','device_observed':False,'target':TARGET}
    def call(tail,data=None):
        result=runner(['adb','-s',serial,*tail],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,check=False)
        if result.returncode!=0:raise RuntimeError('adb_command_failed')
        return result.stdout
    # Device time, not Railway's time; seconds resolution gives conservative expiry.
    stamp=call(['shell','-T','date','+%s']).strip()
    if not re.fullmatch(rb'[0-9]{9,12}',stamp):raise RuntimeError('device_clock_unavailable')
    sample['issued_at_ms']=int(stamp)*1000
    payload=(json.dumps(sample,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    tmp='files/duomove/.fix-'+uuid.uuid4().hex+'.tmp'
    script=f'umask 077; mkdir -p files/duomove && cat > {tmp} && mv {tmp} {REMOTE}'
    try:
        # adb joins remote argv; quote the one fixed script for the remote shell.
        call(['shell','-T','run-as',TARGET,'sh','-c',shlex.quote(script)],payload)
        observed=call(['shell','-T','run-as',TARGET,'cat',REMOTE])
        if observed!=payload:raise RuntimeError('file_readback_mismatch')
    finally:
        # Never remove fix.json on cancellation: another operator may have replaced it.
        try:call(['shell','-T','run-as',TARGET,'rm','-f',tmp])
        except (OSError,RuntimeError,subprocess.TimeoutExpired):pass
    return {'status':'file_readback_verified','generation':sample['generation'],
            'sequence':sample['sequence'],'sha256':hashlib.sha256(payload).hexdigest(),
            'device_observed':False,'target':TARGET}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sample',required=True);p.add_argument('--serial',required=True)
    p.add_argument('--publish',action='store_true',help='Actually write to the owned checker; without this only validate')
    args=p.parse_args()
    try:
        path=Path(args.sample)
        if path.stat().st_size>8192:raise ValueError('sample_too_large')
        result=publish(json.loads(path.read_text()),args.serial,args.publish)
        print(json.dumps(result));return 0
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
        print(json.dumps({'status':'failed','device_observed':False}));return 2
if __name__=='__main__':raise SystemExit(main())
