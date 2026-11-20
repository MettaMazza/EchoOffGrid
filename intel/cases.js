(() => {
  const el = id => document.getElementById('case-' + id);
  const node = (tag, text) => Object.assign(document.createElement(tag), {textContent:text});
  const status = message => { el('status').textContent = message; };
  let page = 0, version = 0, selected = 0, query = new URLSearchParams();
  async function request(url, fields) {
    const options = fields && {method:'POST',body:new URLSearchParams({...fields,token:document.querySelector('#reader-tools').dataset.token})};
    const res = await fetch(url,options);
    const data = await res.json();
    if (!res.ok) throw Error(data.error || 'Request failed');
    return data;
  }
  async function refresh(owner) {
    const data = await request('/openintel/cases?owner='+owner);
    if (owner !== selected) return;
    el('owner').replaceChildren(new Option('Select a case','0'),...data.cases.map(c=>new Option(c.title,c.id)));
    el('owner').value=String(owner);
    el('export').hidden=!owner;
    el('export').href='/openintel/cases/'+owner+'/export';
    el('exhibits').replaceChildren(...data.items.map(r=>{
      const entry=document.createElement('details');
      entry.append(node('summary','['+r.exhibit+'] '+r.title),node('p',r.material+' · '+r.publisher+' · '+r.basis+' '+r.date_utc),
        node('p',r.url||'Local record '+r.key),node('small','SHA-256 '+r.sha256));
      return entry;
    }));
  }
  async function search() {
    const serial=++version;
    const params=new URLSearchParams(query);params.set('page',page);
    const data=await request('/openintel/search?'+params);
    if(serial!==version)return;
    el('results').replaceChildren(...data.rows.map(r=>{
      const card=document.createElement('article');
      const button=node('button','Save to case');
      button.type='button';
      button.onclick=async()=>{
        if(!selected){status('Select or create a case first.');el('owner').focus();return}
        const owner=selected;
        button.disabled=true;
        try{
          await request('/openintel/action',{action:'case-attach',owner,collection:r.collection,key:r.key,version:r.version});
          await refresh(owner);status('Evidence saved to case.');
        }catch(e){status(e.message)}finally{button.disabled=false}
      };
      const date=new Date(r.stamp*1000).toISOString().slice(0,10);
      card.append(node('small',r.collection+' · '+r.material),node('h4',r.title),node('p',r.preview||''),node('small',r.publisher+' · '+r.basis+' '+date),button);
      return card;
    }));
    el('prev').disabled=page===0;el('next').disabled=!data.more;
    el('page').textContent='Page '+(page+1);
    status(data.rows.length?'':'No retained records match this place and date range.');
  }
  function run(fn){fn().catch(e=>status(e.message))}
  el('workspace').ontoggle=()=>{if(el('workspace').open)run(()=>refresh(selected))};
  el('search').onsubmit=e=>{e.preventDefault();query=new URLSearchParams(new FormData(e.target));page=0;run(search)};
  el('create').onsubmit=e=>{e.preventDefault();const form=e.target;run(async()=>{
    const r=await request('/openintel/action',{action:'case-create',title:form.elements.title.value});
    selected=r.id;await refresh(selected);form.reset();status('Case created.');
  })};
  el('owner').onchange=e=>{selected=Number(e.target.value);run(()=>refresh(selected))};
  el('prev').onclick=()=>{if(page>0){page--;run(search)}};
  el('next').onclick=()=>{page++;run(search)};
})();
