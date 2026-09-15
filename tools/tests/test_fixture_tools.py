import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class PublisherTests(unittest.TestCase):
    def sample(self): return {'schema_version':1,'generation':1,'sequence':1,'ttl_ms':10000,'lat':28.0444,'lon':-81.9498,'accuracy':10.0}
    def test_rejects_bad_fields(self):
        p=load('publish_fixture')
        for field,value in [('lat',91),('lon',float('nan')),('speed',-1),('bearing',360),('ttl_ms',30001),('sequence',True),('sequence',1.5),('alt',10),('extra',1)]:
            sample=self.sample();sample[field]=value
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):p.validate(sample)
    def test_optional_values_and_units(self):
        p=load('publish_fixture');s=self.sample();s.update(alt=59.2,altitude_datum='WGS84_ELLIPSOID',speed=12.5,bearing=184.0)
        self.assertEqual(p.validate(s)['speed'],12.5)
    def test_dry_run_never_calls_adb(self):
        p=load('publish_fixture')
        def forbidden(*a,**k):raise AssertionError('adb called')
        result=p.publish(self.sample(),'emulator-5554',False,forbidden)
        self.assertEqual(result['status'],'validated_only');self.assertFalse(result['device_observed'])
    def test_atomic_publish_and_readback(self):
        p=load('publish_fixture');calls=[];written=[]
        def fake(args,**kw):
            calls.append(args)
            if 'date' in args:return subprocess.CompletedProcess(args,0,b'1700000000\n',b'')
            if 'sh' in args:written.append(kw['input']);return subprocess.CompletedProcess(args,0,b'',b'')
            if 'cat' in args:return subprocess.CompletedProcess(args,0,written[-1],b'')
            return subprocess.CompletedProcess(args,0,b'',b'')
        r=p.publish(self.sample(),'emulator-5554',True,fake)
        self.assertEqual(r['status'],'file_readback_verified');self.assertFalse(r['device_observed'])
        self.assertIn('mv', ' '.join(calls[1]));self.assertIn('umask 077', ' '.join(calls[1]));self.assertNotIn('install',' '.join(sum(calls,[])))
        self.assertEqual(json.loads(written[0])['issued_at_ms'],1700000000000)
        self.assertTrue(all(c[:3]==['adb','-s','emulator-5554'] for c in calls))
    def test_real_shell_receives_one_script_and_atomic_file(self):
        import tempfile, shlex
        p=load('publish_fixture')
        with tempfile.TemporaryDirectory() as appdir:
            def local_transport(args,**kw):
                self.assertEqual(args[3:5],['shell','-T'])
                if 'date' in args:return subprocess.CompletedProcess(args,0,b'1700000000\n',b'')
                remote=shlex.split(' '.join(args[5:]))
                self.assertEqual(remote[:2],['run-as',p.TARGET])
                return subprocess.run(remote[2:],cwd=appdir,**kw)
            result=p.publish(self.sample(),'emulator-5554',True,local_transport)
            self.assertEqual(result['status'],'file_readback_verified')
            path=pathlib.Path(appdir)/p.REMOTE
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(path.read_text())['sequence'],1)

    def test_rejects_adb_failure(self):
        p=load('publish_fixture')
        def fake(args,**kw):return subprocess.CompletedProcess(args,1,b'',b'private endpoint secret')
        with self.assertRaises(RuntimeError) as caught:p.publish(self.sample(),'emulator-5554',True,fake)
        self.assertNotIn('private',str(caught.exception))
    def test_rejects_serial_injection(self):
        p=load('publish_fixture')
        with self.assertRaises(ValueError):p.publish(self.sample(),'x;reboot',True)
    def test_metadata_not_accepted_from_host(self):
        p=load('publish_fixture');s=self.sample();s['issued_at_ms']=1
        with self.assertRaises(ValueError):p.validate(s)
    def test_mismatch_is_not_success(self):
        p=load('publish_fixture')
        def fake(args,**kw):return subprocess.CompletedProcess(args,0,b'1700000000\n' if 'date' in args else b'WRONG',b'')
        with self.assertRaises(RuntimeError):p.publish(self.sample(),'emulator-5554',True,fake)

class StaticScopeTests(unittest.TestCase):
    def test_target_and_native_scope(self):
        c=json.loads((ROOT/'android/site-fix/app/src/main/assets/config.json').read_text())
        self.assertEqual(c['pattern'],['net.stakeout.duomove.checker']);self.assertTrue(c['ishook']);self.assertNotIn('libs',c)
    def test_no_network_or_location_permission(self):
        for name in ('app','checker'):
            manifest=(ROOT/f'android/site-fix/{name}/src/main/AndroidManifest.xml').read_text()
            self.assertNotIn('uses-permission',manifest)
    def test_mock_and_time_getters_are_not_hooked(self):
        e=(ROOT/'android/site-fix/app/src/main/java/com/android/dp/Entry.java').read_text()
        for method in ('isMock','isFromMockProvider','getTime','getElapsedRealtimeNanos','getProvider','writeToParcel'):
            self.assertNotIn('"'+method+'"',e)
    def test_core_jvm(self):
        import tempfile
        with tempfile.TemporaryDirectory() as out:
            src=ROOT/'android/site-fix/core/src'
            paths=[*src.glob('main/**/*.java'),*src.glob('test/**/*.java')]
            subprocess.run(['javac','--release','8','-d',out,*map(str,paths)],check=True,capture_output=True)
            r=subprocess.run(['java','-cp',out,'net.stakeout.duomove.fixture.FixTest'],check=True,capture_output=True,text=True)
            self.assertIn('27 checks passed',r.stdout)

if __name__=='__main__':unittest.main()
