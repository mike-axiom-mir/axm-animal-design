#!/usr/bin/env python3
from __future__ import annotations
import argparse, bisect, copy, hashlib, json, math, struct
from pathlib import Path
from typing import Any

SCHEMA='axm.runtime-animal-animation-key-budget/v0.1'
CONTROL_SHA='81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb'
CONTROL_BYTES=10296
RUNTIME_SOURCE_HEAD='e7874c4a8dca1db48bc66f3546c2134f7d724456'
ANIMATION_OWNER_HEAD='eb21e0e0fd888bbb5fa41c73a6c0f1c731f662c2'
TOLERANCE_DEG=0.075
DENSE_RATE=320
DENSE_COUNT=321
CLIP_NAME='quadruped-articulation-loop-001 front-elbow-R UV tangent render-domain keys'


def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def parse_glb(data:bytes)->tuple[dict[str,Any],bytes]:
    magic,version,total=struct.unpack_from('<4sII',data,0)
    if magic!=b'glTF' or version!=2 or total!=len(data): raise ValueError('GLB header drift')
    off=12; doc=None; binary=None
    while off+8<=len(data):
        ln,kind=struct.unpack_from('<I4s',data,off); off+=8
        payload=data[off:off+ln]; off+=ln
        if kind==b'JSON': doc=json.loads(payload.rstrip(b' \t\r\n\x00').decode())
        elif kind in (b'BIN\x00',b'BIN '): binary=payload
    if not isinstance(doc,dict) or binary is None: raise ValueError('GLB chunks missing')
    return doc,binary

def accessor_rows(doc,binary,index):
    acc=doc['accessors'][index]; view=doc['bufferViews'][acc['bufferView']]
    if acc.get('sparse') is not None: raise ValueError('sparse animation accessor unsupported')
    if int(acc['componentType'])!=5126: raise ValueError('animation accessor must be FLOAT')
    width={'SCALAR':1,'VEC4':4}.get(acc['type'])
    if width is None: raise ValueError('unexpected animation accessor type')
    packed=4*width
    if int(view.get('byteStride',packed))!=packed: raise ValueError('interleaved animation accessor unsupported')
    base=int(view.get('byteOffset',0))+int(acc.get('byteOffset',0))
    out=[]
    for i in range(int(acc['count'])):
        vals=list(struct.unpack_from('<'+'f'*width,binary,base+i*packed))
        out.append(vals[0] if width==1 else vals)
    return out

def unit(q):
    n=math.sqrt(sum(float(v)*float(v) for v in q))
    if n<=1e-15: raise ValueError('zero quaternion')
    return [float(v)/n for v in q]

def dot(a,b): return sum(float(x)*float(y) for x,y in zip(a,b))
def slerp(a,b,t):
    qa=unit(a); qb=unit(b); d=dot(qa,qb)
    if d<0: qb=[-v for v in qb]; d=-d
    d=max(-1.0,min(1.0,d))
    if d>0.9995: return unit([(1-t)*qa[i]+t*qb[i] for i in range(4)])
    th=math.acos(d); st=math.sin(th)
    return [math.sin((1-t)*th)/st*qa[i]+math.sin(t*th)/st*qb[i] for i in range(4)]
def qerr_deg(a,b):
    qa=unit(a); qb=unit(b)
    d1=math.sqrt(sum((qa[i]-qb[i])**2 for i in range(4)))
    d2=math.sqrt(sum((qa[i]+qb[i])**2 for i in range(4)))
    return math.degrees(2*math.asin(min(1.0,min(d1,d2)/2)))
def at(times,quats,t):
    if t<=times[0]: return unit(quats[0])
    if t>=times[-1]: return unit(quats[-1])
    i=bisect.bisect_right(times,t)-1
    a=(t-times[i])/(times[i+1]-times[i])
    return slerp(quats[i],quats[i+1],a)

def score(times,quats,keep):
    rt=[times[i] for i in keep]; rq=[quats[i] for i in keep]
    errs=[]
    for si in range(DENSE_COUNT):
        t=si/float(DENSE_RATE)
        errs.append(qerr_deg(at(times,quats,t),at(rt,rq,t)))
    mx=max(errs); wi=errs.index(mx)
    return mx,sum(errs)/len(errs),wi

def simplify(times,quats,tol):
    keep=list(range(len(times)))
    while True:
        best=None
        for pos in range(1,len(keep)-1):
            cand=keep[:pos]+keep[pos+1:]
            mx,mean,wi=score(times,quats,cand)
            if mx<=tol:
                row=(mx,mean,keep[pos],wi,cand)
                if best is None or row[:4]<best[:4]: best=row
        if best is None: break
        keep=best[4]
    return keep,score(times,quats,keep)

def make_glb(doc,binary):
    js=json.dumps(doc,separators=(',',':')).encode('utf-8')
    js+=b' '*((-len(js))%4)
    bb=binary+b'\x00'*((-len(binary))%4)
    total=12+8+len(js)+8+len(bb)
    return struct.pack('<4sII',b'glTF',2,total)+struct.pack('<I4s',len(js),b'JSON')+js+struct.pack('<I4s',len(bb),b'BIN\x00')+bb

def build(control:bytes):
    if sha(control)!=CONTROL_SHA or len(control)!=CONTROL_BYTES: raise ValueError('exact control identity drift')
    doc,binary=parse_glb(control)
    anims=doc.get('animations',[])
    if len(anims)!=1 or len(anims[0].get('channels',[]))!=1: raise ValueError('expected exact one-channel animation')
    ch=anims[0]['channels'][0]; sam=anims[0]['samplers'][ch['sampler']]
    if ch.get('target',{}).get('path')!='rotation' or sam.get('interpolation')!='LINEAR': raise ValueError('animation semantics drift')
    ia,oa=int(sam['input']),int(sam['output'])
    times=[float(v) for v in accessor_rows(doc,binary,ia)]
    quats=[[float(v) for v in row] for row in accessor_rows(doc,binary,oa)]
    if len(times)!=41 or len(quats)!=41: raise ValueError('authored key count drift')
    if abs(times[0])>1e-9 or abs(times[-1]-1.0)>1e-6: raise ValueError('duration drift')
    keep,(mx,mean,wi)=simplify(times,quats,TOLERANCE_DEG)
    iv=doc['bufferViews'][doc['accessors'][ia]['bufferView']]; ov=doc['bufferViews'][doc['accessors'][oa]['bufferView']]
    ib=int(iv.get('byteOffset',0))+int(doc['accessors'][ia].get('byteOffset',0))
    ob=int(ov.get('byteOffset',0))+int(doc['accessors'][oa].get('byteOffset',0))
    il=41*4; ol=41*16
    if ib+il!=ob or ob+ol!=len(binary): raise ValueError('animation accessors must be terminal contiguous tail')
    traw=binary[ib:ib+il]; qraw=binary[ob:ob+ol]
    nt=b''.join(traw[i*4:(i+1)*4] for i in keep)
    nq=b''.join(qraw[i*16:(i+1)*16] for i in keep)
    nb=binary[:ib]+nt+nq
    nd=copy.deepcopy(doc)
    nd['accessors'][ia]['count']=len(keep); nd['accessors'][oa]['count']=len(keep)
    nd['bufferViews'][nd['accessors'][ia]['bufferView']]['byteLength']=len(nt)
    nd['bufferViews'][nd['accessors'][oa]['bufferView']]['byteOffset']=ib+len(nt)
    nd['bufferViews'][nd['accessors'][oa]['bufferView']]['byteLength']=len(nq)
    nd['buffers'][0]['byteLength']=len(nb)
    cand=make_glb(nd,nb)
    return cand,{
      'schema':SCHEMA,'state':'PASS_RUNTIME_ANIMAL_ANIMATION_KEY_BUDGET_CANDIDATE_BUILT',
      'control_sha256':CONTROL_SHA,'candidate_sha256':sha(cand),'runtime_source_head':RUNTIME_SOURCE_HEAD,
      'animation_owner_head':ANIMATION_OWNER_HEAD,'control_keys':41,'candidate_keys':len(keep),
      'key_reduction':41-len(keep),'key_reduction_percent':(41-len(keep))*100.0/41.0,
      'control_animation_accessor_bytes':820,'candidate_animation_accessor_bytes':len(nt)+len(nq),
      'animation_accessor_bytes_saved':820-(len(nt)+len(nq)),
      'control_glb_bytes':len(control),'candidate_glb_bytes':len(cand),'glb_bytes_saved':len(control)-len(cand),
      'glb_percent_saved':(len(control)-len(cand))*100.0/len(control),'tolerance_deg':TOLERANCE_DEG,
      'dense_rate_hz':DENSE_RATE,'dense_samples':DENSE_COUNT,'max_quaternion_residual_deg':mx,
      'mean_quaternion_residual_deg':mean,'worst_sample_index':wi,'worst_time_s':wi/DENSE_RATE,
      'kept_authored_indices':keep,'motion_retimed':False,'source_authored_keys_modified':False,
      'truth_boundary':'Bounded representation candidate only. No Art/QA, target-device, gameplay, CANON or production claim.'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--control-glb',required=True); ap.add_argument('--out-dir',required=True); args=ap.parse_args()
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    control=Path(args.control_glb).read_bytes(); cand,report=build(control)
    (out/'control.glb').write_bytes(control); (out/'candidate.glb').write_bytes(cand)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    req={'width':960,'height':720,'playback':None,'poses':[{'clip':CLIP_NAME,'time_s':report['worst_time_s']},{'clip':CLIP_NAME,'time_s':0.5}], 'views':[
      {'clip':CLIP_NAME,'time_s':report['worst_time_s'],'yaw':0.72,'elevation':0.32},
      {'clip':CLIP_NAME,'time_s':report['worst_time_s'],'yaw':-0.58,'elevation':0.16},
      {'clip':CLIP_NAME,'time_s':0.5,'yaw':0.72,'elevation':0.32}]}
    (out/'request.json').write_text(json.dumps(req,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
