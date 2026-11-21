(() => {
  const root=document.querySelector('#visual-browser');
  if(!root)return;
  const el=id=>document.getElementById(id);
  const node=(tag,value)=>{const n=document.createElement(tag);n.textContent=value;return n};
  const button=(label,handle)=>{const b=node('button',label);b.type='button';b.onclick=handle;return b};
  const date=el('visual-date'), kind=el('visual-kind'), provider=el('visual-provider');
  const region=()=>el('intel-region').value;
  date.max=new Date().toISOString().slice(0,10);
  date.value=new Date(Date.now()-86400000).toISOString().slice(0,10);
  const dialog=el('visual-detail'), pane=el('visual-content');
  let page=0, version=0, request=0, timer;
  const stamp=seconds=>new Date(seconds*1000).toISOString().slice(0,19).replace('T',' ')+' UTC';
  const savedFrames=new Map();
  function frameKey(r){return [r.id,region(),date.value].join('|')}
  async function action(fields){
    const body=new URLSearchParams({region:region(),...fields,token:document.querySelector('#reader-tools').dataset.token});
    const reply=await fetch('/openintel/action',{method:'POST',body});
    const data=await reply.json();if(!reply.ok)throw Error(data.error||'Publisher unavailable');return data
  }
  function anchor(label,url){const a=node('a',label);a.href=url;return a}
  const comparison = el('compare-dates'), frames = el('compare-frames'), message = el('compare-status');
  let comparisonVersion = 0;
  for (const [name, days] of [['earlier', 2], ['later', 1]]) {
    comparison.elements[name].max = date.max;
    comparison.elements[name].value = new Date(Date.now() - days * 86400000).toISOString().slice(0,10);
  }
  function resetComparison() {
    comparisonVersion++;
    message.textContent = '';
    frames.replaceChildren();
  }
  comparison.oninput = resetComparison;
  document.addEventListener('intel-region-change',resetComparison);
  comparison.onsubmit = async event => {
    event.preventDefault();
    resetComparison();
    const version = comparisonVersion;
    const {earlier,later,sensor} = comparison.elements;
    if (earlier.value >= later.value) {
      message.textContent = 'Choose two different days in chronological order.';
      return;
    }
    const place = region(), instrument = sensor.value, label = sensor.selectedOptions[0].text;
    message.textContent = 'NASA GIBS · '+label+' · '+el('intel-region').selectedOptions[0].text+
      '. Each image combines observations over one UTC day. Clouds and missing swaths can obscure changes.';
    await Promise.all([earlier.value,later.value].map(async day => {
      const figure = document.createElement('figure');
      frames.append(figure);
      const heading = node('h4',day+' UTC'), details = node('p','Checking local archive…');
      figure.append(heading,details);
      async function render() {
        const params = new URLSearchParams({region:place,sensor:instrument,day});
        const response = await fetch('/openintel/composite?'+params);
        const result = await response.json();
        if (version !== comparisonVersion) return;
        if (!response.ok) throw Error(result.error || 'Local archive unavailable');
        if (!result) {
          details.textContent = 'No local image for this day.';
          const acquire = button('Fetch and save image',async () => {
            acquire.disabled = true;
            try {
              const capture = await action({action:'visual-frame',id:instrument,day});
              // Keep the request paired with its original region if the user navigates away.
              await action({action:'save',region:place,id:capture.id,at:capture.received});
              await render();
            } catch (err) {details.textContent = err.message;acquire.disabled = false}
          });
          figure.replaceChildren(heading,details,acquire);
          return;
        }
        const image = document.createElement('img');
        image.src = result.image;image.alt = label+' daily composite for '+day;
        image.onerror = () => {details.textContent='The stored image could not be displayed.'};
        details.textContent = 'Retrieved '+stamp(result.received)+' · '+result.projection;
        figure.replaceChildren(heading,image,details,anchor('Publisher image ↗',result.url));
      }
      try {await render()} catch (err) {details.textContent = err.message}
    }));
  };
  function show(row){
    const serial=++request;
    pane.replaceChildren(node('small',row.kind+' · '+row.publisher),node('h3',row.title),node('p',row.area));
    const display=document.createElement('div'), actions=document.createElement('div'),status=node('output','');
    actions.className='visual-actions';pane.append(display,status,actions,anchor('Publisher and coverage ↗',row.url));
    function photo(url,label){const img=document.createElement('img');img.src=url;img.alt=label;display.replaceChildren(img)}
    async function load(){
      const key=frameKey(row);
      status.textContent='Fetching image from '+row.publisher+'…';refresh.disabled=true;
      try{
        const result=await action({action:'visual-frame',id:row.id,day:date.value});
        if(serial!==request)return;
        savedFrames.set(key,result);photo(result.image,row.title);
        status.textContent=(row.publisher==='NASA GIBS'?'Composite day '+date.value+' · ':'')+'Fetched '+stamp(result.received)+(result.modified?' · Publisher file modified '+stamp(result.modified):'');
        if(result.id){
          const save=button('Save to Library',async()=>{save.disabled=true;try{await action({action:'save',id:result.id,at:result.received});save.textContent='Saved to Library'}catch(e){save.disabled=false;status.textContent=e.message}});
          actions.querySelector('[data-save]')?.remove();save.dataset.save='1';actions.append(save);
        }
        if(result.bounds){
          const overlay=button('Show on map',()=>{dialog.close();el('intel-map').contentWindow.postMessage({openintel:'overlay',value:{url:result.image,bounds:result.bounds}},location.origin);el('intel-map').scrollIntoView({block:'center'})});
          actions.querySelector('[data-overlay]')?.remove();overlay.dataset.overlay='1';actions.append(overlay)
        }
      }catch(e){if(serial===request)status.textContent=e.message}
      finally{refresh.disabled=false}
    }
    const refresh=button('Refresh image',load);
    if(row.image)actions.append(refresh);
    if(row.video){
      actions.append(anchor(row.kind==='Publisher viewer'?'Open camera viewer ↗':'Watch video',row.video));
    }
    if(row.poster){photo(row.poster,'Bundled example · '+row.example);status.textContent=row.example}
    if(!dialog.open)dialog.showModal();
    if(row.image)load()
  }
  el('visual-close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{request++;pane.replaceChildren()});
  async function browse(network=false){
    const seq=++version;
    try{
      const q=new URLSearchParams({region:region(),day:date.value,kind:kind.value,publisher:provider.value,q:el('visual-search').value,page});
      const response=await fetch('/openintel/visuals?'+q);const model=await response.json();
      if(seq!==version)return;if(!response.ok)throw Error(model.error);
      page=model.page;
      const was=provider.value;provider.replaceChildren(new Option('All publishers',''),...model.publishers.map(p=>new Option(p,p)));provider.value=was;
      const cards=el('visual-cards');cards.replaceChildren();
      const jobs=[];
      for(const row of model.rows){
        const card=button('',()=>show(row));card.className='visual-card';
        const art=document.createElement('span');art.className='visual-art';
        function photo(url){const img=document.createElement('img');img.alt='';img.src=url;img.loading='lazy';art.replaceChildren(img)}
        const cached=savedFrames.get(frameKey(row));
        if(cached)photo(cached.image);else if(row.poster)photo(row.poster);
        else {art.textContent=row.kind==='Live video'?'▶ Watch live':row.kind==='Camera clip'?'▶ Play clip':row.kind==='Publisher viewer'?'↗ Open viewer':'View camera';
          if(network&&row.image)jobs.push(async()=>{
            const key=frameKey(row);
            try{const result=await action({action:'visual-frame',id:row.id,day:date.value});if(seq===version){savedFrames.set(key,result);photo(result.image)}}catch{if(seq===version)art.textContent='Preview unavailable'}
          })}
        card.append(art,node('small',row.kind+' · '+row.publisher),node('strong',row.title),node('span',row.area));
        if(row.poster&&!cached)card.append(node('small',row.example));
        cards.append(card)
      }
      el('visual-count').textContent=model.count.toLocaleString()+' sources · '+(model.pages?'Page '+(page+1)+' of '+model.pages:'No matches')+' · Directory checked '+model.checked;
      el('visual-prev').disabled=page===0;el('visual-next').disabled=page+1>=model.pages;
      for(let i=0;i<jobs.length&&seq===version;i+=2)await Promise.all(jobs.slice(i,i+2).map(f=>f()))
    }catch(e){if(seq===version)el('visual-count').textContent=e.message}
  }
  for(const control of [kind,provider,date])control.onchange=()=>{if(control===kind)provider.value='';page=0;browse(true)};
  el('visual-search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{page=0;browse(true)},300)};
  el('visual-prev').onclick=()=>{page--;browse(true)};el('visual-next').onclick=()=>{page++;browse(true)};
  document.addEventListener('intel-region-change',()=>{page=0;browse()});
  let satellites=[];
  function options(){
    const q=el('orbit-find').value.toLowerCase();
    const matches=satellites.filter(s=>(s.name+' '+s.number+' '+s.group).toLowerCase().includes(q));
    el('orbit-choice').replaceChildren(...matches.map(s=>new Option(s.name+' · '+s.number,s.number)));
    if(!matches.length)el('orbit-detail').textContent='No matching objects';
  }
  el('orbit-explorer').ontoggle=async()=>{
    if(!el('orbit-explorer').open||satellites.length)return;
    try{satellites=await (await fetch('/openintel/orbits')).json();options()}catch{el('orbit-detail').textContent='Orbital catalogue unavailable'}
  };
  el('orbit-find').oninput=options;
  async function orbit(refresh){
    const number=el('orbit-choice').value;if(!number)return;
    const out=el('orbit-detail');out.textContent='Calculating orbit…';
    try{
      const r=await action({action:'orbit-choice',number,refresh:refresh?'1':'0'});
      out.textContent=r.title+' · predicted at '+stamp(r.time)+' · elements dated '+stamp(r.epoch)+' · '+(r.window?'Next pass above 10° from the selected region: '+stamp(r.window.start)+' to '+stamp(r.window.end)+' · peak '+r.window.peak+'°':'No pass above 10° in the next 36 hours.');
      el('intel-map').contentWindow.postMessage({openintel:'orbit',value:r},location.origin);
    }catch(e){out.textContent=e.message}
  }
  el('orbit-form').onsubmit=e=>{e.preventDefault();orbit(false)};
  el('orbit-refresh').onclick=()=>orbit(true);
  window.addEventListener('DOMContentLoaded',()=>browse());
})();
