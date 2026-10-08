'use client';
import {useState} from 'react';
import QuantPane from './QuantPane';
import ExperimentalPane from './ExperimentalPane';
import type {Context} from '@/lib/api';
export default function QuantWorkspace({context,environment}:{context:Context;environment?:string}) {
  const [advanced,setAdvanced]=useState(false);
  return <><div className="row wrap mb12" role="tablist" aria-label="Quant workspace">
    <button className={`button ${!advanced?'primary':''}`} role="tab" aria-selected={!advanced} onClick={()=>setAdvanced(false)}>Canonical Quant Lab</button>
    <button className={`button ${advanced?'primary':''}`} role="tab" aria-selected={advanced} onClick={()=>setAdvanced(true)}>Advanced Research Laboratory</button>
  </div>{advanced?<ExperimentalPane context={context} environment={environment}/>:<QuantPane context={context}/>}</>;
}
