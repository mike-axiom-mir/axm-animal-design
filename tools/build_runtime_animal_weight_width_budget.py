#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from axm_animal_design.runtime_weight_width_budget import FLOAT, UNSIGNED_SHORT, compact_weights_0_to_normalized_u16, parse_glb, sha256_bytes

TECHNICAL_ART_HEAD='54c9c11505e798a56619ebc14e9ab41f522eef70'
CONTROL_SHA='8d9bfb80369bda09eaad786a35833cd5e04da5e608211f53648daaa1cde29566'
CONTROL_BYTES=10948
UC_HEAD='e6826acbc7296ba77d25534c8d3d3770ff3fa747'
UC_CODEC='capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js'
UC_CODEC_BLOB='b1f2e68bb6c6800af5496decc95a8044d141edc9'
VERTICES=84; TRIANGLES=80
SCHEMA='axm.runtime-animal-weight-width-budget/v0.1'; STATE='PASS_ANIMAL_WEIGHT_WIDTH_COMPACTION_PAYLOAD_AND_UC_RECEIVER'

def git_head(path:Path)->str: return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
def git_blob(path:Path,p:str)->str: return subprocess.check_output(['git','-C',str(path),'rev-parse',f'HEAD:{p}'],text=True).strip()
def numeric_delta(a:Any,b:Any)->float:
    if isinstance(a,bool) or isinstance(b,bool): return 0.0 if a==b else float('inf')
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return abs(float(a)-float(b))
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b): return max((numeric_delta(x,y) for x,y in zip(a,b)),default=0.0)
    if isinstance(a,dict) and isinstance(b,dict) and set(a)==set(b): return max((numeric_delta(a[k],b[k]) for k in a),default=0.0)
    return 0.0 if a==b else float('inf')
def inspect(root:Path,glb:Path)->dict[str,Any]:
    script="const fs=require('fs');const c=require(process.argv[1]);const b=new Uint8Array(fs.readFileSync(process.argv[2]));process.stdout.write(JSON.stringify(c.inspect(b)));"
    return json.loads(subprocess.check_output(['node','-e',script,str((root/UC_CODEC).resolve()),str(glb.resolve())],text=True))
def require_uc(v:dict[str,Any],label:str)->None:
    if v.get('pass') is not True or v.get('vertices')!=VERTICES or v.get('triangles')!=TRIANGLES: raise ValueError(f'{label} UC geometry failed')
    if v.get('weightSumsPass') is not True or v.get('jointIndicesPass') is not True or v.get('deformation',{}).get('pass') is not True: raise ValueError(f'{label} UC skin/deformation failed')

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--control-glb',type=Path,required=True); ap.add_argument('--uc-root',type=Path,required=True); ap.add_argument('--runtime-head',required=True); ap.add_argument('--out-dir',type=Path,required=True); args=ap.parse_args()
    if git_head(args.uc_root)!=UC_HEAD or git_blob(args.uc_root,UC_CODEC)!=UC_CODEC_BLOB: raise ValueError('UC identity drift')
    control=args.control_glb.read_bytes()
    if sha256_bytes(control)!=CONTROL_SHA or len(control)!=CONTROL_BYTES: raise ValueError('current Technical Art GLB identity drift')
    c=compact_weights_0_to_normalized_u16(control); candidate=c.candidate_bytes
    cp=parse_glb(control); np=parse_glb(candidate); ca=cp.document['accessors'][c.accessor_index]; na=np.document['accessors'][c.accessor_index]
    if ca['componentType']!=FLOAT or bool(ca.get('normalized',False)): raise ValueError('control WEIGHTS_0 drift')
    if na['componentType']!=UNSIGNED_SHORT or na.get('normalized') is not True: raise ValueError('candidate WEIGHTS_0 drift')
    if len(c.control_rows)!=VERTICES or c.control_payload_bytes!=1344 or c.candidate_payload_bytes!=672: raise ValueError('bounded weight payload drift')
    if c.max_abs_weight_error>1.0/65535.0+1e-12 or c.max_row_sum_error>1e-12: raise ValueError('quantization error boundary failed')
    if not c.non_weight_hashes_identical or len(candidate)>=len(control): raise ValueError('payload identity/size gate failed')
    args.out_dir.mkdir(parents=True,exist_ok=True); co=args.out_dir/'control-f32-weights.glb'; no=args.out_dir/'candidate-u16norm-weights.glb'; co.write_bytes(control); no.write_bytes(candidate)
    cu=inspect(args.uc_root,co); nu=inspect(args.uc_root,no); require_uc(cu,'control'); require_uc(nu,'candidate')
    clip=str(cp.document['animations'][0]['name'])
    request={'width':960,'height':720,'poses':[{'clip':clip,'time_s':t} for t in (0.0,0.25,0.5,0.75,1.0)],'views':[{'clip':clip,'time_s':0.5,'yaw':0.72,'elevation':0.32},{'clip':clip,'time_s':0.5,'yaw':-0.58,'elevation':0.16}],'playback':None}
    (args.out_dir/'request.json').write_text(json.dumps(request,indent=2,sort_keys=True)+'\n')
    saved=c.control_payload_bytes-c.candidate_payload_bytes; total_saved=len(control)-len(candidate)
    report={'schema':SCHEMA,'state':STATE,'runtime_head':args.runtime_head,'technical_art_head':TECHNICAL_ART_HEAD,'control_glb_sha256':CONTROL_SHA,'universal_creation':{'head':UC_HEAD,'codec_blob':UC_CODEC_BLOB,'product_modified':False},'representation':{'render_vertices':VERTICES,'weight_slots_per_vertex':4,'control_component_type':FLOAT,'control_normalized':False,'candidate_component_type':UNSIGNED_SHORT,'candidate_normalized':True,'control_weight_payload_bytes':c.control_payload_bytes,'candidate_weight_payload_bytes':c.candidate_payload_bytes,'weight_payload_saved_bytes':saved,'weight_payload_reduction_fraction':saved/c.control_payload_bytes,'control_glb_bytes':len(control),'candidate_glb_bytes':len(candidate),'total_glb_saved_bytes':total_saved,'total_glb_reduction_fraction':total_saved/len(control),'candidate_glb_sha256':sha256_bytes(candidate),'max_abs_decoded_weight_error':c.max_abs_weight_error,'max_candidate_row_sum_error':c.max_row_sum_error,'non_weight_accessor_payload_hashes_identical':True},'current_uc_receiver':{'control_pass':True,'candidate_pass':True,'deformation_receipt_max_numeric_delta':numeric_delta(cu.get('deformation'),nu.get('deformation'))},'visual_review_boundary':{'state':'PENDING_REAL_GODOT_IMPORT_RENDER_A_B'},'truth_boundary':{'does_not_prove':['deformed normal/tangent direction-frame equivalence','target-device FPS/CPU/GPU/VRAM/heap improvement','generic sparse/interleaved/multi-primitive safety','automatic Technical Art or UC adoption','CANON or production readiness']}}
    (args.out_dir/'build-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); (args.out_dir/'uc-control.json').write_text(json.dumps(cu,indent=2,sort_keys=True)+'\n'); (args.out_dir/'uc-candidate.json').write_text(json.dumps(nu,indent=2,sort_keys=True)+'\n')
    print(STATE); print(json.dumps(report['representation'],sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
