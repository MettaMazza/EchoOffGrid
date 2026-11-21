(() => {
  const root=document.querySelector('#openintel');
  if (!root) return;
  const $=s=>root.querySelector(s), all=s=>Array.from(root.querySelectorAll(s));
  const query=new URLSearchParams(location.search);
  let region=query.get('region')||localStorage.getItem('intel-region')||'aberdeen';
  let mode=query.get('view')||'reports', at=Number(query.get('at'))||0, selected=query.get('item')||'';
  let firstVisit=!query.has('view')&&!query.has('item'),model,playing=false,live=false,request=0,polling=false,zoomPending=false;
  const disabled=new Set(), token=document.querySelector('#reader-tools').dataset.token;
  const colors={'Aircraft':'#a8daed','Vessels':'#7fd5b9','Cameras':'#e3ba88','Satellites':'#c8a9eb','Earth imagery':'#dbabca','Hazards & sea':'#f0b48e','Local receiver':'#d6d58d'};
  const text=(tag,value)=>{const n=document.createElement(tag);n.textContent=value;return n};
  const button=(value,fn)=>{const b=text('button',value);b.type='button';b.onclick=fn;return b};
  const clock=t=>new Date(t*1000).toISOString().slice(0,16).replace('T',' ')+' UTC';
  const say=s=>$('#intel-message').textContent=s;
  function map(action,value){$('#intel-map').contentWindow.postMessage({openintel:action,value},location.origin)}
  function age(t){const n=Math.max(0,model.now-t);return n<60?'under a minute ago':n<3600?Math.floor(n/60)+' min ago':n<86400?Math.floor(n/3600)+' h ago':Math.floor(n/86400)+' d ago'}
  function route(){
    const q=new URLSearchParams({region,view:mode});if(at)q.set('at',at);if(selected)q.set('item',selected);
    history.replaceState(null,'','/openintel?'+q)
  }
  function pick(id,locate=false){$('#intel-detail').hidden=false;$('#intel-reopen').hidden=true;selected=id;zoomPending=locate;route();render()}
  async function post(action,fields={}){
    const body=new URLSearchParams({token,action,region});
    for(const [k,v] of Object.entries(fields)){for(const value of [].concat(v))body.append(k,value)}
    const r=await fetch('/openintel/action',{method:'POST',body});
    const result=await r.json();if(!r.ok)throw Error(result.error||'Request failed');return result
  }
  async function load(){
    const seq=++request;
    try{
      const r=await fetch('/openintel/data?'+new URLSearchParams({region,at,view:mode}),{cache:'no-store'});
      const data=await r.json();if(seq!==request)return;
      if(!r.ok)throw Error(data.error||'Could not load observations');
      if(firstVisit){firstVisit=false;if(!data.rows.length&&mode==="reports"&&!at){await view("sample");return}}
      model=data;render()
    }catch(e){if(seq===request)say(e.message)}
  }
  function setLive(on){
    live=on;$('#intel-live').setAttribute('aria-pressed',String(on));$('#intel-live').textContent=on?'Pause live updates':'Start live updates'
  }
  async function update(){
    if(!live||polling||document.hidden||mode!=='reports'||at||!model)return;
    polling=true;
    try{await post('refresh',{sources:Object.keys(model.sources).filter(s=>!disabled.has(model.sources[s].layer))});await load()}
    catch(e){say(e.message)}finally{polling=false}
  }
  const trackDialog = $('#track-history');
  let trackRequest = 0, trackPage = 0, trackQuery;
  async function trackReports(page) {
    const serial = ++trackRequest;
    const summary = $('#track-summary'), list = $('#track-reports');
    const prev = $('#track-prev'), next = $('#track-next');
    prev.disabled = next.disabled = true;
    summary.textContent = 'Loading local reports…';
    list.replaceChildren();
    try {
      const response = await fetch('/openintel/history?' + new URLSearchParams({...trackQuery, page}));
      const data = await response.json();
      if (serial !== trackRequest) return;
      if (!response.ok) throw Error(data.error || 'Could not open report history');
      trackPage = page;
      const publisher = text('a',data.publisher);
      publisher.href = data.url;
      summary.replaceChildren(publisher, document.createTextNode(' · '+trackQuery.object+' · '+(data.rows.length ?
        'Newest first. Intervals over 15 minutes are marked as gaps.' : 'No retained reports for this selection.')));
      for (const row of data.rows) {
        const item = document.createElement('li');
        item.append(text('strong', 'Observed '+new Date(row.time*1000).toISOString()),
          text('span', row.lat.toFixed(4)+'°, '+row.lon.toFixed(4)+'° · '+row.detail));
        if (row.received) item.append(text('small','Retrieved '+clock(row.received)));
        if (/^https:\/\/(api\.adsb\.lol|meri\.digitraffic\.fi)\//.test(row.retrieval_url || '')) {
          const link = text('a','Publisher feed ↗');
          link.href = row.retrieval_url;
          item.append(link);
        }
        if (row.revises) item.append(text('small','Earlier record revised'));
        if (row.interval > data.gap_seconds) item.append(text('em','Gap before this report · '+Math.round(row.interval/60)+' min'));
        list.append(item);
      }
      prev.disabled = page === 0;
      next.disabled = !data.more;
    } catch (err) {
      if (serial === trackRequest) { summary.textContent = err.message; prev.disabled = page === 0; }
    }
  }
  $('#track-close').onclick = () => trackDialog.close();
  trackDialog.onclose = () => {if (!trackDialog.open) trackRequest++};
  $('#track-prev').onclick = () => trackReports(trackPage-1);
  $('#track-next').onclick = () => trackReports(trackPage+1);
  function openTrack(row) {
    trackQuery = {region, source:row.source, object:row.object, until:at || model.now};
    $('#track-title').textContent = row.title+' · Report history';
    trackDialog.showModal();
    trackReports(0);
  }
  function render(){
    if(!model)return;
    all('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===mode)));
    const src=model.sources,needle=$('#intel-find').value.trim().toLowerCase();
    const rows=model.rows.filter(r=>!disabled.has(src[r.source].layer)&&(!needle||[r.title,src[r.source].title,r.detail].join(' ').toLowerCase().includes(needle)));
    const visible=rows.map(r=>({...r,color:colors[src[r.source].layer],stale:r.source!=='orbit'&&model.at-r.time>Math.max(900,src[r.source].interval*3)}));
    let r=selected?rows.find(v=>v.id===selected):rows[0];
    const cameraPin={id:'publisher-maui',lat:20.716,lon:-156.448,color:colors.Cameras};
    const mapped=mode==='reports'&&!at&&!disabled.has('Cameras')&&['maui','world'].includes(region)?visible.concat(cameraPin):visible;
    map('view',{rows:mapped.filter(x=>!x.no_map_point),center:model.center,key:region,selected:r?.id});
    if(zoomPending&&r){zoomPending=false;if(!r.no_map_point)map('locate',[r.lon,r.lat])}
    const list=$('#intel-rows');list.replaceChildren();
    for(const row of rows.slice(0,120)){
      const b=button('',()=>pick(row.id,true));b.className='intel-result';b.style.setProperty('--layer',colors[src[row.source].layer]);
      if(row.id===r?.id)b.setAttribute('aria-current','true');
      if(row.media){const img=document.createElement('img');img.src='/openintel/image/'+row.id;img.alt='';img.loading='lazy';b.append(img)}
      b.append(text('small',src[row.source].layer),text('strong',row.title),text('span',row.source==='orbit'?'Predicted position':clock(row.time)));list.append(b)
    }
    $('#intel-count').textContent=rows.length+' '+(mode==='sample'?'sample observations':mode==='saved'?'saved observations':'observations')+(rows.length>120?' · first 120 listed':'');
    const detail=$('#intel-detail');detail.replaceChildren();
    if(r){
      const info=src[r.source];detail.style.setProperty('--layer',colors[info.layer]);
      detail.append(text('small',mode==='sample'?'OFFLINE SAMPLE':r.source==='orbit'?'PREDICTED':r.source==='local'?'RECEIVED LOCALLY':info.layer.toUpperCase()),text('h3',r.title));
      if(r.media){const img=document.createElement('img');img.src='/openintel/image/'+r.id;img.alt=r.title;detail.append(img)}
      detail.append(text('p',r.detail),text('strong',r.source==='orbit'?'Predicted for '+clock(r.time):(r.source==='imagery'?'Composite day · '+clock(r.time).slice(0,10):(r.time_basis||'Observed')+' '+clock(r.time))),text('span',(r.publisher||info.title)+' · '+info.rights));
      if(r.received)detail.append(text('span','Fetched '+clock(r.received)));
      if(mode!=='sample' && ['air','ships'].includes(r.source)) detail.append(button('View report history',()=>openTrack(r)));
      if(r.source==='ais') detail.append(text('small','AISStream provides live positions only. This feed has no retained track history.'));
      if(r.epoch){detail.append(text('span','Orbital elements '+clock(r.epoch)));
        detail.append(text('p',r.window?'Pass above 10° · '+clock(r.window.start)+' to '+clock(r.window.end)+' · peak '+r.window.peak+'°':'No pass above 10° in the next 36 hours.'))}
      if(!r.no_map_point)detail.append(text('span',r.lat.toFixed(3)+'°, '+r.lon.toFixed(3)+'°'));
      if(!at&&mode==='reports'&&r.source!=='orbit')detail.append(text('small','Last report '+age(r.time)));
      if(mode!=='sample'&&r.source!=='ais'){
        const save=button(r.saved?'Saved to Library':'Save observation',async()=>{save.disabled=true;try{await post('save',{id:r.id,at:r.time});await load();say('Saved to Library → Documents')}catch(e){save.disabled=false;say(e.message)}});
        save.disabled=Boolean(r.saved);detail.append(save)
      }
      if(innerWidth<=650){
        const collapse=button('Close details',()=>{detail.hidden=true;$('#intel-reopen').hidden=false;$('#intel-map').scrollIntoView({block:'center'})});
        detail.append(collapse)
      }
    } else {
      detail.append(text('h3',selected?'Selected report unavailable':mode==='saved'?'No saved observations here':'No matching observations'),
        text('p',selected?'This exact report is outside this view or has expired. Select another report to continue.':mode==='saved'?'Save an observation from Latest to keep it here.':'Choose another layer or region, start live updates, or explore the offline samples.'))
    }
    const images=rows.filter(item=>item.media&&item.source==='imagery'&&r&&r.source==='imagery'&&item.id!==r.id);
    if(images.length){
      const compare=text('select','');compare.setAttribute('aria-label','Compare another imagery date');
      compare.add(new Option('Compare another date…',''));
      for(const image of images)compare.add(new Option(clock(image.time).slice(0,10),image.id));
      const preview=document.createElement('img');preview.hidden=true;
      compare.onchange=()=>{preview.hidden=!compare.value;if(compare.value){preview.src='/openintel/image/'+compare.value;preview.alt=compare.selectedOptions[0].text}};
      detail.append(compare,preview)
    }
    const slider=$('#intel-time');slider.min=Math.min(model.earliest,at||model.now);slider.max=model.now;slider.value=at||model.now;
    slider.disabled=mode!=='reports'||model.earliest===model.now;
    $('#intel-clock').textContent=at?clock(at):'Latest reports';
    $('#intel-play').disabled=slider.disabled;$('#intel-now').disabled=!at;
    all('[data-provider]').forEach(card=>{
      const id=card.dataset.provider;let status=card.querySelector('output');
      if(!status){status=text('output','');card.append(status)}
      const v=model.status[id];status.textContent=v?v.note+' · checked '+clock(v.attempt):id==='ais'?(model.keySet?'Session key connected':'Requires a session key'):''
    })
  }
  function stopPlay(){playing=false;$('#intel-play').textContent='▶ Replay'}
  async function view(v){mode=v;selected='';at=0;stopPlay();if(v!=='reports')setLive(false);route();await load()}
  all('[data-view]').forEach(b=>b.onclick=()=>view(b.dataset.view));
  all('[data-layer]').forEach(b=>{b.style.setProperty('--layer',colors[b.dataset.layer]);b.onclick=()=>{const k=b.dataset.layer;if(disabled.has(k))disabled.delete(k);else disabled.add(k);b.setAttribute('aria-pressed',String(!disabled.has(k)));render()}});
  $('#intel-live').onclick=async()=>{if(!live){await view('reports');setLive(true);await update();say('Live updates on while this tab is visible.')}else{setLive(false);say('Live updates paused.')}};
  async function change(k){
    region=k;localStorage.setItem('intel-region',k);selected='';at=0;stopPlay();
    const menu=$('#intel-region');
    if(!Array.from(menu.options).some(o=>o.value===k))menu.add(new Option(k,k),menu.options.length-1);
    menu.value=k;document.dispatchEvent(new Event('intel-region-change'));route();await load();await update()
  }
  $('#intel-region').onchange=e=>{const custom=e.target.value==='custom';$('#intel-custom').hidden=!custom;if(!custom)change(e.target.value)};
  $('#intel-custom').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);$('#intel-custom').hidden=true;change(Number(f.get('lat')).toFixed(3)+','+Number(f.get('lon')).toFixed(3))};
  $('#intel-reopen').onclick=()=>{pick(selected);$('#intel-detail').scrollIntoView({block:'nearest'})};
  $('#intel-find').oninput=render;
  $('#intel-time').oninput=e=>{stopPlay();setLive(false);at=+e.target.value;route();load()};
  $('#intel-now').onclick=()=>view('reports');
  $('#intel-play').onclick=()=>{if(playing){stopPlay();return}setLive(false);playing=true;if(!at)at=model.earliest;$('#intel-play').textContent='Ⅱ Pause';route();load()};
  setInterval(()=>{if(playing&&model){at+=Math.max(1,Math.ceil((model.now-model.earliest)/100));if(at>=model.now){at=0;stopPlay()}route();load()}},750);
  setInterval(()=>{if(!document.hidden&&live)load()},5000);setInterval(update,30000);
  $('#intel-catalog-search').oninput=e=>all('[data-provider]').forEach(c=>c.hidden=!c.textContent.toLowerCase().includes(e.target.value.toLowerCase()));
  $('#intel-key').onsubmit=async e=>{e.preventDefault();try{await post('key',{key:e.target.elements.key.value});e.target.reset();await load();say('AISStream session key connected.')}catch(err){say(err.message)}};
  $('#intel-forget').onclick=async()=>{await post('key',{key:''});await load();say('Session key forgotten.')};
  $('#intel-imagery').elements.day.value=new Date(Date.now()-86400000).toISOString().slice(0,10);
  $('#intel-imagery').onsubmit=async e=>{e.preventDefault();if(region==='world'){say('Choose a smaller region for an imagery pack.');return}
    try{await view('reports');await post('refresh',{sources:['imagery'],day:e.target.elements.day.value});say('Acquiring regional imagery…');for(const delay of [1200,4000,9000])setTimeout(load,delay)}catch(err){say(err.message)}};
  $('#intel-import').onsubmit=async e=>{e.preventDefault();try{const file=e.target.elements.file.files[0];if(file.size>12000)throw Error('Choose a GeoJSON file under 12 KB');
    const result=await post('import',{geojson:await file.text()});await view('reports');say('Imported '+result.count+' receiver observations.')}catch(err){say(err.message)}};
  addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==$('#intel-map').contentWindow)return;if(e.data.openintel==='ready')render();if(e.data.openintel==='select'&&e.data.value==='publisher-maui'){
    const camera=$('[data-provider=maui]');camera.closest('details').open=true;camera.scrollIntoView({block:'center'});
    camera.querySelector('#intel-player,a[href="/openintel/camera"]')?.focus();return
  }if(e.data.openintel==='select'){pick(e.data.value);if(innerWidth<=650)$('#intel-detail').scrollIntoView({block:'nearest'})}});
  if(!Array.from($('#intel-region').options).some(o=>o.value===region))$('#intel-region').add(new Option(region,region),$('#intel-region').options.length-1);
  $('#intel-region').value=region;load()
})();
