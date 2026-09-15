#!/usr/bin/env python3
import argparse, json, os
from pathlib import Path
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

DEFAULT_MODEL='facebook/nllb-200-distilled-600M'
SRC_LANG='rus_Cyrl'
TGT_LANG='eng_Latn'

def atomic_save_json(data,path):
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
    os.replace(tmp,path)

def srt_timestamp(seconds):
    ms=max(0,round(float(seconds)*1000)); h,rem=divmod(ms,3600000); m,rem=divmod(rem,60000); s,ms=divmod(rem,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def write_srt(data,path):
    lines=[]; n=1
    for seg in data.get('segments',[]):
        text=str(seg.get('translation','')).strip()
        if not text: continue
        lines += [str(n),f"{srt_timestamp(seg['start'])} --> {srt_timestamp(seg['end'])}",text,'']; n+=1
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text('\n'.join(lines),encoding='utf-8'); os.replace(tmp,path)

def load_model(name,device_name):
    device='cuda' if device_name=='auto' and torch.cuda.is_available() else ('cpu' if device_name=='auto' else device_name)
    print(f'Device: {device}')
    tok=AutoTokenizer.from_pretrained(name,src_lang=SRC_LANG,tgt_lang=TGT_LANG)
    if device=='cuda': model=AutoModelForSeq2SeqLM.from_pretrained(name,torch_dtype=torch.float16).to(device)
    else: model=AutoModelForSeq2SeqLM.from_pretrained(name).to(device)
    model.eval(); return tok,model,device

def translate_batch(texts,tok,model,device):
    inputs=tok(texts,return_tensors='pt',padding=True,truncation=True,max_length=512)
    inputs={k:v.to(device) for k,v in inputs.items()}
    with torch.inference_mode():
        out=model.generate(**inputs,forced_bos_token_id=tok.convert_tokens_to_ids(TGT_LANG),num_beams=4,max_new_tokens=128)
    return tok.batch_decode(out,skip_special_tokens=True)

def main():
    p=argparse.ArgumentParser(description='Translate Russian Whisper JSON to English with NLLB while preserving timings.')
    p.add_argument('--input',required=True); p.add_argument('--output',required=True); p.add_argument('--srt-output')
    p.add_argument('--model',default=DEFAULT_MODEL); p.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    p.add_argument('--batch-size',type=int,default=4); p.add_argument('--start',type=int,default=0); p.add_argument('--limit',type=int); p.add_argument('--save-every',type=int,default=25)
    a=p.parse_args(); inp=Path(a.input); out=Path(a.output)
    with inp.open(encoding='utf-8') as f: input_data=json.load(f)
    if not isinstance(input_data.get('segments'),list): raise ValueError("Input JSON does not contain a 'segments' array.")
    if out.exists():
        with out.open(encoding='utf-8') as f: data=json.load(f)
        if len(data.get('segments',[]))!=len(input_data['segments']): raise ValueError('Existing output has a different number of segments than the input.')
    else: data=json.loads(json.dumps(input_data))
    segs=data['segments']; total=len(segs); start=max(0,a.start); stop=total if a.limit is None else min(total,start+max(0,a.limit))
    print(f'Segments: {total} | range: {start}..{stop-1}')
    tok,model,device=load_model(a.model,a.device); since=0
    for bs in range(start,stop,a.batch_size):
        be=min(stop,bs+a.batch_size); idx=[]; texts=[]
        for i in range(bs,be):
            if str(segs[i].get('translation','')).strip(): continue
            text=str(segs[i].get('text','')).strip()
            if text: idx.append(i); texts.append(text)
            else: segs[i]['translation']=''
        if idx:
            for i,t in zip(idx,translate_batch(texts,tok,model,device)): segs[i]['translation']=t.strip(); since+=1
        print(f'Processed through segment {be-1}')
        if since>=a.save_every:
            atomic_save_json(data,out); print(f'Progress saved: {out}'); since=0
    atomic_save_json(data,out)
    srt=Path(a.srt_output) if a.srt_output else out.with_name(out.stem+'_en.srt'); write_srt(data,srt)
    print(f'Done. JSON: {out}\nSRT: {srt}')

if __name__=='__main__': main()
