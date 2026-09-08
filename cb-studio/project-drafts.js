/* Local text drafts only. Never restores approval checkboxes, files or credentials. */
(() => {
  'use strict';
  const prefix='studio.draft.v1.', bindings=new WeakMap();
  // A duplicated browser tab clones sessionStorage. A new writer ID per document
  // plus per-field recovery pointers prevents those tabs overwriting one another.
  const tab=crypto.randomUUID();
  const secret=value=>/\b(?:sk-[A-Za-z0-9_-]{12,}|ark-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,})/.test(value);
  function bind(element,scope,{revision='',meta=()=>({}),restore=()=>{},reset=false}={}){
    if(!element||element.type==='password'||element.type==='file'||element.type==='checkbox')return;
    const base=prefix+JSON.stringify(scope)+'.',key=base+tab,old=bindings.get(element);
    if(old?.key===key)return;
    old?.stop();
    let status=document.createElement('small');status.className='sp-draft-status';status.setAttribute('role','status');element.after(status);
    const read=()=>{try{
      const own=localStorage.getItem(key);if(own)return JSON.parse(own);
      const owner=sessionStorage.getItem(base+'owner'),previous=owner&&localStorage.getItem(base+owner);
      if(previous)return JSON.parse(previous);
      return Object.keys(localStorage).filter(k=>k.startsWith(base)).map(k=>{try{return JSON.parse(localStorage.getItem(k));}catch{return null;}}).filter(Boolean).sort((a,b)=>b.at-a.at)[0];
    }catch{return null;}};
    const draft=read();
    if(draft&&!secret(String(draft.value||''))){try{localStorage.setItem(key,JSON.stringify(draft));sessionStorage.setItem(base+'owner',tab);}catch{}}
    if(old&&reset)element.value='';
    if(draft&&typeof draft.value==='string'&&draft.value&&!secret(draft.value)){
      element.value=draft.value;if(draft.value)restore(draft.meta||{});
      status.textContent=draft.value?'Draft restored on this browser'+(draft.revision!==revision?' · production has changed; review before sending':'')+'.':'';
    }
    const save=()=>{
      if(secret(element.value)){status.textContent='API keys belong in Workspace connections. This draft was not saved.';try{localStorage.removeItem(key);}catch{}return;}
      try{localStorage.setItem(key,JSON.stringify({value:element.value,meta:meta(),revision,at:Date.now()}));sessionStorage.setItem(base+'owner',tab);status.textContent=element.value?'Draft saved on this browser.':'';}
      catch{status.textContent='Draft could not be saved on this browser. Keep this page open or copy your text.';}
    };
    element.addEventListener('input',save);element.addEventListener('change',save);
    const b={key,save,clear(value){
      try {const current=JSON.parse(localStorage.getItem(key)||'null');if(!current||current.value===value){localStorage.setItem(key,JSON.stringify({value:'',revision,at:Date.now()}));sessionStorage.setItem(base+'owner',tab);}}catch{}
      if(bindings.get(element)===b&&element.value===value){element.value='';status.textContent='';}
    },stop(){element.removeEventListener('input',save);element.removeEventListener('change',save);status.remove();}};
    bindings.set(element,b);return b;
  }
  function clear(element,value=element?.value){bindings.get(element)?.clear(value);}
  function form(root,scope,names,revision=''){
    for(const name of names)bind(root.elements?.[name]||root.querySelector(`[name="${name}"]`),[...scope,name],{revision});
  }
  // New episode forms are rebuilt by the project page. Bind text, never the submit action.
  const projectForms=()=>{
    if(typeof CURRENT_PROJECT==='undefined'||!CURRENT_PROJECT)return;
    for(const id of ['projectPartTitle','projectPartScript','projectPartSummary']){
      bind(document.getElementById(id),[CURRENT_PROJECT.id,'new-episode',id]);
    }
  };
  new MutationObserver(projectForms).observe(document.documentElement,{childList:true,subtree:true});
  window.StudioDrafts={bind,clear,form,save:element=>bindings.get(element)?.save(),capture:element=>{const b=bindings.get(element),value=element?.value;return ()=>b?.clear(value);}};
})();
