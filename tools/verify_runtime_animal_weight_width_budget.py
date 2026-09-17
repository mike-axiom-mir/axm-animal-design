#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
from PIL import Image

BUILD_SCHEMA='axm.runtime-animal-weight-width-budget/v0.1'; BUILD_STATE='HOLD_ANIMAL_WEIGHT_WIDTH_COMPACTION__CURRENT_UC_RIGGED_CODEC_FLOAT_ONLY'
FINAL_SCHEMA='axm.runtime-animal-weight-width-budget-report/v0.1'; FINAL_STATE='HOLD_ANIMAL_GLB_WEIGHT_WIDTH_COMPACTION__CURRENT_UC_RIGGED_CODEC_FLOAT_ONLY'
CONTROL_SHA='8d9bfb80369bda09eaad786a35833cd5e04da5e608211f53648daaa1cde29566'; TECHNICAL_ART_HEAD='54c9c11505e798a56619ebc14e9ab41f522eef70'
POSE_TOLERANCE=2e-6; EXPECTED_UC_ERROR='WEIGHTS_0 accessor invalid'

def load(path:Path)->dict[str,Any]:
    value=json.loads(path.read_text());
    if not isinstance(value,dict): raise ValueError(f'{path} must contain object')
    return value
def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def numeric_delta(a:Any,b:Any)->float:
    if isinstance(a,bool) or isinstance(b,bool): return 0.0 if a==b else float('inf')
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return abs(float(a)-float(b))
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b): return max((numeric_delta(x,y) for x,y in zip(a,b)),default=0.0)
    if isinstance(a,dict) and isinstance(b,dict) and set(a)==set(b): return max((numeric_delta(a[k],b[k]) for k in a),default=0.0)
    return 0.0 if a==b else float('inf')
def require_backend(receipt:dict[str,Any],label:str)->None:
    backend=receipt.get('backend',{})
    if not str(backend.get('version','')).startswith('4.7.2') or backend.get('renderer')!='gl_compatibility' or backend.get('display')=='headless': raise ValueError(f'{label} backend drift: {backend}')
def image_delta(left:Path,right:Path)->dict[str,Any]:
    li=Image.open(left).convert('RGBA'); ri=Image.open(right).convert('RGBA')
    if li.size!=ri.size: raise ValueError(f'{left.name} size drift')
    changed=0; maximum=0; total_abs=0
    for a,b in zip(li.getdata(),ri.getdata()):
        channels=[abs(int(a[i])-int(b[i])) for i in range(4)]; delta=max(channels)
        if delta: changed+=1; maximum=max(maximum,delta); total_abs+=sum(channels)
    total=li.size[0]*li.size[1]
    return {'control_sha256':sha(left),'candidate_sha256':sha(right),'byte_identical':sha(left)==sha(right),'changed_pixels':changed,'total_pixels':total,'changed_pixel_fraction':changed/total,'max_channel_delta':maximum,'sum_abs_channel_delta':total_abs}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--build-report',type=Path,required=True); ap.add_argument('--control-root',type=Path,required=True); ap.add_argument('--candidate-root',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    build=load(args.build_report); rep=build.get('representation',{}); receiver=build.get('current_uc_receiver',{})
    if build.get('schema')!=BUILD_SCHEMA or build.get('state')!=BUILD_STATE or build.get('technical_art_head')!=TECHNICAL_ART_HEAD: raise ValueError('build identity drift')
    if receiver.get('control_pass') is not True or receiver.get('candidate_pass') is not False or receiver.get('blocking_error')!=EXPECTED_UC_ERROR or EXPECTED_UC_ERROR not in receiver.get('candidate_errors',[]): raise ValueError('current UC receiver HOLD identity drift')
    if rep.get('control_component_type')!=5126 or rep.get('candidate_component_type')!=5123 or rep.get('candidate_normalized') is not True: raise ValueError('weight component contract drift')
    if rep.get('control_weight_payload_bytes')!=1344 or rep.get('candidate_weight_payload_bytes')!=672 or rep.get('weight_payload_saved_bytes')!=672: raise ValueError('expected exact 672-byte weight payload reduction')
    if rep.get('max_abs_decoded_weight_error',1)>1.0/65535.0+1e-12 or rep.get('max_candidate_row_sum_error',1)>1e-12: raise ValueError('weight quantization boundary drift')
    if rep.get('non_weight_accessor_payload_hashes_identical') is not True or rep.get('candidate_glb_bytes',0)>=rep.get('control_glb_bytes',0): raise ValueError('payload identity/size gate failed')
    control=load(args.control_root/'worker-result.json'); candidate=load(args.candidate_root/'worker-result.json'); require_backend(control,'control'); require_backend(candidate,'candidate')
    if control.get('source_sha256')!=CONTROL_SHA or candidate.get('source_sha256')!=rep.get('candidate_glb_sha256'): raise ValueError('Godot source identity drift')
    cp=control.get('poses'); np=candidate.get('poses')
    if not isinstance(cp,list) or not isinstance(np,list) or len(cp)!=5 or len(np)!=5: raise ValueError('expected five pose observations')
    pose_delta=numeric_delta(cp,np)
    if pose_delta>POSE_TOLERANCE: raise ValueError(f'pose receipt delta {pose_delta} exceeds {POSE_TOLERANCE}')
    if any(int(p.get('triangles',-1))!=80 for p in cp+np): raise ValueError('triangle count drift')
    if numeric_delta(control.get('material_bindings'),candidate.get('material_bindings'))!=0.0: raise ValueError('material binding drift')
    names=('view-00.png','view-00-coverage.png','view-01.png','view-01-coverage.png'); pairs={name:image_delta(args.control_root/name,args.candidate_root/name) for name in names}
    coverage=[pairs[name] for name in names if 'coverage' in name]
    if any(pair['changed_pixels'] for pair in coverage): raise ValueError('coverage mask changed')
    visible=[pairs[name] for name in names if 'coverage' not in name]; changed=sum(pair['changed_pixels'] for pair in visible); max_channel=max(pair['max_channel_delta'] for pair in visible)
    visual_state='NONE_OBSERVED__TWO_FIXED_VIEWS_BYTE_IDENTICAL' if changed==0 else 'NONZERO_FIXED_VIEW_PIXEL_DELTA__ART_DIRECTOR_REVIEW_REQUIRED'
    report={'schema':FINAL_SCHEMA,'state':FINAL_STATE,'runtime_head':build.get('runtime_head'),'technical_art_head':TECHNICAL_ART_HEAD,'representation':rep,'current_uc_receiver':receiver,'godot_import':{'control_backend':control.get('backend'),'candidate_backend':candidate.get('backend'),'pose_observations_per_mode':5,'maximum_control_candidate_pose_receipt_delta':pose_delta,'pose_tolerance':POSE_TOLERANCE,'material_bindings_identical':True,'candidate_imported_despite_current_uc_codec_hold':True},'visual_tradeoff':{'state':visual_state,'visible_changed_pixels_total':changed,'visible_max_channel_delta':max_channel,'coverage_masks_identical':True,'image_pairs':pairs,'art_director_review_note':'Any nonzero fixed-view pixel delta belongs to Art Direction. Runtime does not erase it. The larger blocker is current UC rigged-gltf-codec requiring FLOAT WEIGHTS_0.'},'decision':'HOLD_TECHNICAL_ART_WEIGHT_STORAGE_ADOPTION__CURRENT_UC_RIGGED_CODEC_FLOAT_ONLY','truth_boundary':{'proves':['the current 84-vertex Technical Art GLB has a 1,344-byte FLOAT WEIGHTS_0 payload','normalized u16 cuts that accessor payload to 672 bytes while preserving all non-weight accessor payload hashes and keeping decoded scalar error within one u16-normalized step','current UC rigged-gltf-codec rejects the candidate specifically at its FLOAT-only WEIGHTS_0 accessor gate','real Godot 4.7.2 GL Compatibility imports both representations and stays within the retained pose/visual bounds measured here'],'does_not_prove':['that UC should widen its receiver without Technical Art/UC-owner review','deformed normal/tangent owner-frame equivalence','target-device CPU/GPU/FPS/VRAM/heap improvement','arbitrary skin/import safety','Art Direction acceptance if visible delta is nonzero','CANON or production readiness']}}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(FINAL_STATE); print(json.dumps({'pose_delta':pose_delta,'visual_state':visual_state,'changed_pixels':changed,'max_channel_delta':max_channel,'glb_saved_bytes':rep['total_glb_saved_bytes'],'uc_blocker':EXPECTED_UC_ERROR},sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
