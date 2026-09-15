#!/usr/bin/env python3
"""Copy only verified kit build inputs; never copy native hooks or vendor caches."""
import argparse
import hashlib
from pathlib import Path
import zipfile

BRIDGE_SHA='b23fd0b42ae82a46e58a8e5581ce1fb39dffc2b64003f6f88efc936959741099'
EXPECTED={
    'app/src/main/libs/dpbridge.jar':BRIDGE_SHA,
    'gradlew':'63135287117a1e6d12c84580f1f49c61d1ba02218ecd28660605e97f976e7d65',
    'gradlew.bat':'af835f98787e9269af5a046edcb821a592fed372139df7b947b471a63cfc236b',
    'gradle/wrapper/gradle-wrapper.jar':'e996d452d2645e70c01c11143ca2d3742734a28da2bf61f25c82bdc288c9e637'}
ROOT=Path(__file__).resolve().parents[1]/'android/site-fix'

def prepare(archive,root=ROOT):
    with zipfile.ZipFile(archive) as z:
        for name in EXPECTED:
            if z.getinfo('dplus_demo/'+name).file_size>2_000_000:raise ValueError('Kit input too large')
        inputs={
            'app/src/main/libs/dpbridge.jar':z.read('dplus_demo/app/src/main/libs/dpbridge.jar'),
            'gradlew':z.read('dplus_demo/gradlew'),
            'gradlew.bat':z.read('dplus_demo/gradlew.bat'),
            'gradle/wrapper/gradle-wrapper.jar':z.read('dplus_demo/gradle/wrapper/gradle-wrapper.jar')}
    for name,data in inputs.items():
        if hashlib.sha256(data).hexdigest()!=EXPECTED[name]:
            raise ValueError('Unrecognized kit input; inspect the new vendor kit before accepting it')
    for name,data in inputs.items():
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (root/'gradlew').chmod(0o755)
    (root/'gradle/wrapper/gradle-wrapper.properties').write_text(
        'distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\n'
        'distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip\n'
        'zipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('zip');args=p.parse_args()
    prepare(args.zip);print('Verified dpbridge.jar copied; no native libraries or vendor caches copied.')
