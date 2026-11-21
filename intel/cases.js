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
  const placeForm=el('places'), placeStatus=el('places-status'), placeResults=el('places-results');
  let placePage=0, placeVersion=0;
  async function findPlaces(page) {
    const version=++placeVersion, region=document.getElementById('intel-region').value;
    const query=new URLSearchParams({region,clue:placeForm.elements.clue.value,page});
    placeStatus.textContent='Searching the local extract…';
    const data=await request('/openintel/places?'+query);
    if(version!==placeVersion)return;
    placePage=page;
    el('places-next').disabled=!data.more;
    el('places-prev').disabled=!page;
    placeStatus.textContent=data.acquired
      ? data.count+' matches in the regional extract · © OpenStreetMap contributors · '+(data.snapshot || new Date(data.acquired*1000).toISOString())+(data.capped?' · first 3,000 features indexed':'')
      : 'Download landmarks for the selected region to search them offline.';
    placeResults.replaceChildren(...data.rows.map(row=>{
      const card=document.createElement('article'), original=node('a','OpenStreetMap record ↗');
      original.href=row.url;
      const locate=node('button','Show on map'), save=node('button','Save to case');
      locate.onclick=()=>{
        const frame=document.getElementById('intel-map');
        frame.contentWindow.postMessage({openintel:'landmark',value:{title:row.title,lat:row.lat,lon:row.lon}},location.origin);
        frame.scrollIntoView({block:'center'});
      };
      save.onclick=()=>run(async()=>{
        const owner=selected;
        if(!owner){placeStatus.textContent='Select or create a case first.';el('owner').focus();return;}
        save.disabled=true;
        try {
          await request('/openintel/action',{action:'case-landmark',region,owner,feature:row.key,digest:data.digest});
          await refresh(owner);placeStatus.textContent='Landmark and original extract saved to case.';
        } finally {save.disabled=false;}
      });
      card.append(node('h4',row.title),node('p',row.kinds.join(' · ')),node('small',
        (row.centre?'Feature centre':'Mapped point')+' · '+row.lat.toFixed(4)+'°, '+row.lon.toFixed(4)+'°'),
        original,locate,save);
      return card;
    }));
  }
  const mapFrame=document.getElementById('intel-map');
  el('map-clues').onclick=()=>{
    const query=placeForm.elements.clue.value.trim();
    if(!query){placeStatus.textContent='Enter a landmark name or feature type.';return;}
    const serial=++placeVersion;
    placeResults.replaceChildren();el('places-next').disabled=true;el('places-prev').disabled=true;
    placeStatus.textContent='Searching visible map tiles…';
    mapFrame.contentWindow.postMessage({openintel:'clue-search',value:{query,serial}},location.origin);
  };
  window.addEventListener('message',event=>{
    if(event.origin!==location.origin||event.source!==mapFrame.contentWindow||event.data?.openintel!=='clue-results')return;
    const data=event.data.value;
    if(data.serial!==placeVersion)return;
    if(data.error){placeStatus.textContent=data.error;return;}
    placeStatus.textContent=data.rows.length+' map matches · '+data.basemap+' · © OpenStreetMap contributors / Protomaps. Zoom in for finer detail. Up to 50 results.';
    placeResults.replaceChildren(...data.rows.map(row=>{
      const button=node('button',row.title+' · '+row.kind);
      button.onclick=()=>{mapFrame.contentWindow.postMessage({openintel:'landmark',value:row},location.origin);mapFrame.scrollIntoView({block:'center'});};
      return button;
    }));
  });
  placeForm.onsubmit=event=>{event.preventDefault();run(()=>findPlaces(0));};
  el('places-prev').onclick=()=>run(()=>findPlaces(placePage-1));
  el('places-next').onclick=()=>run(()=>findPlaces(placePage+1));
  el('places-fetch').onclick=()=>run(async()=>{
    const button=el('places-fetch'),region=document.getElementById('intel-region').value;
    button.disabled=true;placeStatus.textContent='Downloading regional landmarks…';
    try {
      await request('/openintel/action',{action:'places-fetch',region});
      if(region===document.getElementById('intel-region').value)await findPlaces(0);
    } catch(err){placeStatus.textContent=err.message;} finally {button.disabled=false;}
  });
  document.addEventListener('intel-region-change',()=>{placeVersion++;placeResults.replaceChildren();placeStatus.textContent='';
    el('places-prev').disabled=true;el('places-next').disabled=true;});
  const coverage = el('coverage');
  const now = Date.now();
  for (const [field, offset] of [['start', 120], ['end', 0]]) {
    coverage.elements[field].value = new Date(now - offset * 60000).toISOString().slice(0, 16);
  }
  let coverageVersion = 0;
  function clearCoverage() {
    coverageVersion++;
    el('coverage-results').replaceChildren();
    el('coverage-status').textContent = '';
  }
  document.addEventListener('intel-region-change', clearCoverage);
  coverage.addEventListener('input', clearCoverage);
  coverage.onsubmit = async event => {
    event.preventDefault();
    clearCoverage();
    const current = coverageVersion;
    const params = new URLSearchParams(new FormData(coverage));
    params.set('region', document.getElementById('intel-region').value);
    try {
      const data = await request('/openintel/coverage?' + params);
      if (current !== coverageVersion) return;
      const rows = data.sources.filter(r => r.count);
      const missing = data.sources.filter(r => !r.count);
      el('coverage-status').textContent = data.region + ' · ' + rows.length + ' sources with retained records in this window. Times use the record date. Orbital predictions and daily composites have their own time resolution.';
      const list = document.createElement('ul');
      const utc = stamp => new Date(stamp * 1000).toISOString().replace('T',' ').slice(0,19);
      for (const r of rows) list.append(node('li',r.title+' · '+r.count+' · '+utc(r.first)+' to '+utc(r.last)+' UTC'));
      const gaps = document.createElement('details');
      gaps.append(node('summary','Sources without retained records ('+missing.length+')'));
      for (const r of missing) gaps.append(node('p', r.title+' · '+r.access));
      el('coverage-results').replaceChildren(list,gaps);
    } catch (err) {
      if (current === coverageVersion) el('coverage-status').textContent = err.message;
    }
  };
  async function refresh(owner) {
    const data = await request('/openintel/cases?owner='+owner);
    if (owner !== selected) return;
    el('owner').replaceChildren(new Option('Select a case','0'),...data.cases.map(c=>new Option(c.title,c.id)));
    el('owner').value=String(owner);
    el('export').hidden=!owner;
    el('export').href='/openintel/cases/'+owner+'/export';
    el('analysis').hidden=!owner;
    const exhibits=new Map(data.items.map(r=>[r.ref,r]));
    const timeline=[];
    for(const r of data.items){
      if(r.date_utc)timeline.push([r.date_utc,r.basis,'['+r.exhibit+'] '+r.title]);
      if(r.retrieved_utc)timeline.push([r.retrieved_utc,'Retrieved','['+r.exhibit+'] '+r.title]);
    }
    for(const f of data.findings)timeline.push([f.written_utc,'Finding recorded',f.statement]);
    for(const edge of data.relationships) timeline.push([edge.written_utc,'Relationship reviewed',edge.subject+' · '+edge.predicate+' · '+edge.object]);
    timeline.sort(([a],[b])=>a.localeCompare(b));
    el('timeline').replaceChildren(...timeline.map(([when,basis,title])=>{
      const li=document.createElement('li'),time=node('time',when.replace('T',' ').replace('+00:00',' UTC'));
      time.dateTime=when;li.append(time,node('small',basis),node('span',title));return li;
    }));
    el('links').replaceChildren(node('legend','Evidence for this finding'),...data.items.map(r=>{
      const label=node('label','['+r.exhibit+'] '+r.title+' ');
      const role=document.createElement('select');
      role.name=r.ref;
      role.append(new Option('Unlinked',''),new Option('Supports','supports'),new Option('Contradicts','contradicts'));
      label.append(role);return label;
    }));
    const evidenceSelect = el('relationship').elements.ref;
    const priorRef = evidenceSelect.value;
    evidenceSelect.replaceChildren(new Option('Select a saved exhibit',''),...data.items.map(r=>new Option('['+r.exhibit+'] '+r.title,r.ref)));
    if (exhibits.has(priorRef)) evidenceSelect.value = priorRef;
    el('relationships').replaceChildren(...data.relationships.map(edge=>{
      const card = document.createElement('article'), exhibit = exhibits.get(edge.exhibit_ref);
      card.append(node('h4',edge.subject+' · '+edge.predicate+' · '+edge.object),
        node('small',edge.assessment+' · '+edge.written_utc),
        node('p',edge.passage),node('p',exhibit?'['+exhibit.exhibit+'] '+exhibit.title:'Cited exhibit unavailable'));
      return card;
    }));
    el('findings').replaceChildren(...data.findings.map(f=>{
      const card=document.createElement('article');
      card.append(node('small',f.written_utc),node('h4',f.statement));
      for(const [ref,role] of Object.entries(f.links)){
        const r=exhibits.get(ref);
        if(r)card.append(node('p','['+r.exhibit+'] '+r.title+' · '+role));
      }
      if(f.unknowns)card.append(node('p','Still unknown: '+f.unknowns));
      return card;
    }));
    el('exhibits').replaceChildren(...data.items.map(r=>{
      const entry=document.createElement('details');
      entry.append(node('summary','['+r.exhibit+'] '+r.title),node('p',r.material+' · '+r.publisher+' · '+r.basis+' '+r.date_utc),
        node('p',r.url||'Local record '+r.key),node('small','SHA-256 '+r.sha256));
      const original=node('a','Review saved original');
      original.href='/openintel/cases/'+owner+'/exhibits/'+r.ref;
      entry.append(original);
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
  const requestedOwner=Number(new URLSearchParams(location.search).get('case'));
  if(Number.isSafeInteger(requestedOwner)&&requestedOwner>0){selected=requestedOwner;el('workspace').open=true;}
  el('create').onsubmit=e=>{e.preventDefault();const form=e.target;run(async()=>{
    const r=await request('/openintel/action',{action:'case-create',title:form.elements.title.value});
    selected=r.id;await refresh(selected);form.reset();status('Case created.');
  })};
  el('relationship').onsubmit = event => {
    event.preventDefault();
    const form = event.target, owner = selected, submit = form.querySelector('button');
    const fields = Object.fromEntries(new FormData(form));
    submit.disabled = true;
    run(async () => {
      try {
        await request('/openintel/action',{...fields,owner,action:'case-relationship'});
        if (selected === owner) { form.reset();await refresh(owner);status('Relationship saved.'); }
      } finally { submit.disabled = false; }
    });
  };
  el('finding').onsubmit=e=>{e.preventDefault();const form=e.target,owner=selected;
    const links=Object.fromEntries([...el('links').querySelectorAll('select')].filter(x=>x.value).map(x=>[x.name,x.value]));
    const submit=form.querySelector('button');submit.disabled=true;
    run(async()=>{try{
      await request('/openintel/action',{action:'case-finding',owner,statement:form.elements.statement.value,unknowns:form.elements.unknowns.value,links:JSON.stringify(links)});
      if(owner===selected){form.reset();await refresh(owner);status('Finding saved.')}
    }finally{submit.disabled=false}});
  };
  el('owner').onchange=e=>{el('finding').reset();el('relationship').reset();selected=Number(e.target.value);run(()=>refresh(selected))};
  el('prev').onclick=()=>{if(page>0){page--;run(search)}};
  el('next').onclick=()=>{page++;run(search)};
})();
