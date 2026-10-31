"""Exercise packaged backend startup, HTTP assets and database persistence."""
import json,os,subprocess,sys,tempfile,time,urllib.request,http.cookiejar
from pathlib import Path
root=Path(__file__).resolve().parents[1]
exe=root/'backend-dist'/('ledgerly-backend.exe' if sys.platform=='win32' else 'ledgerly-backend')
with tempfile.TemporaryDirectory() as data:
 def start():
  log=Path(data)/'startup.log'
  output=log.open('w')
  process=subprocess.Popen([str(exe)],env={**os.environ,'PORT':'0','LEDGERLY_DATA_DIR':data},stdout=output,stderr=subprocess.STDOUT)
  try:
   for _ in range(300):
    if process.poll() is not None:raise RuntimeError(log.read_text())
    for line in log.read_text().splitlines():
     if line.startswith('LEDGERLY_READY='):return process,output,line.split('=',1)[1]
    time.sleep(.1)
   raise RuntimeError('Packaged backend startup timed out')
  except BaseException:
   process.terminate();process.wait(timeout=10);output.close();raise
 def stop(process,output):
  process.terminate();process.wait(timeout=10);output.close()
 process,output,url=start()
 try:
  assert urllib.request.urlopen(url,timeout=5).status==200
  opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  credentials=json.dumps(dict(username='smoke-owner',password='temporary-smoke-password')).encode()
  with opener.open(urllib.request.Request(url+'/api/bootstrap',data=credentials,headers={'Content-Type':'application/json'}),timeout=10) as response:json.load(response)
  payload=json.dumps(dict(name='Packaging check',batch='SMOKE',price=112,tax=12,tax_inclusive=True,mrp=112,pack_size=10)).encode()
  request=urllib.request.Request(url+'/api/products',data=payload,headers={'Content-Type':'application/json'})
  result=json.load(opener.open(request,timeout=5))
  assert result['products'][0]['name']=='Packaging check'
 finally:stop(process,output)
 process,output,url=start()
 try:
  with opener.open(urllib.request.Request(url+'/api/login',data=credentials,headers={'Content-Type':'application/json'}),timeout=10) as response:json.load(response)
  with opener.open(url+'/api/state',timeout=5) as response:result=json.load(response)
  assert len(result['products'])==1,'Database did not survive restart'
 finally:stop(process,output)
print('Packaged backend startup, assets and persistence passed')
