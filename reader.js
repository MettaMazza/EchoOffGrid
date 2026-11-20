(() => {
  const bar = document.querySelector('.speech');
  if (!bar) return;
  const main = document.querySelector('main');
  const popup = document.querySelector('#read-selection');
  const button = id => document.getElementById('read-' + id);
  const clock = button('clock'), seek = button('seek'), rate = button('speed');
  const savedRate=document.cookie.match(/(?:^|; )echo_read_speed=([0-9.]+)(?:;|$)/);
  if(savedRate && [...rate.options].some(option=>parseFloat(option.value)===Number(savedRate[1])))
    rate.value=[...rate.options].find(option=>parseFloat(option.value)===Number(savedRate[1])).value;
  const player = new Audio();
  player.preservesPitch = true;
  const cache = new Map();
  let chunks = [], lengths = [], index = 0, paused = false, loading = false;
  let selected = '', track = 0, jump = 0, blob = '', request = new AbortController();

  function time(value) {
    const seconds = Math.floor(Math.max(0,value));
    return Math.floor(seconds/60) + ':' + String(seconds%60).padStart(2,'0');
  }
  function elapsed() { return lengths.slice(0,index).reduce((a,b)=>a+b,0) + (player.currentTime || 0); }
  function total() { return lengths.reduce((a,b)=>a+b,0); }
  function display() {
    const active = chunks.length > 0;
    button('pause').disabled = !active; button('stop').disabled = !active && !loading;
    button('pause').textContent = paused ? 'Resume' : 'Pause'; seek.disabled = !active;
    const end = total(), now = active ? elapsed() : 0;
    if (document.activeElement !== seek || !seek.matches(':active')) seek.value = end ? Math.round(now/end*1000) : 0;
    clock.textContent = active ? time(now)+' / '+(lengths.length>1?'≈':'')+time(end) : '0:00';
    seek.setAttribute('aria-valuetext',clock.textContent);
  }
  function stop(message) {
    track++; jump++; request.abort(); request = new AbortController();
    player.onended=null;player.onerror=null; player.pause();
    player.removeAttribute('src'); player.load();
    if(blob) URL.revokeObjectURL(blob);
    blob=''; cache.clear(); chunks=[]; lengths=[]; index=0; paused=false; loading=false;
    button('status').textContent=message || 'Emma · Offline voice'; display();
  }
  function split(text) {
    const parts=[]; let part='';
    for (const word of text.trim().split(/\s+/u)) {
      if (part.length+word.length>155 || (part.length>65 && /[.!?…][”"']?$/.test(part))) {
        if(part)parts.push(part);part='';
      }
      if(word.length>155){for(let n=0;n<word.length;n+=155)parts.push(word.slice(n,n+155));}
      else part += (part?' ':'') + word;
    }
    if(part)parts.push(part);
    return parts.filter(p=>/[\p{L}\p{N}]/u.test(p));
  }
  const native=window.echoAudio;
  const send=(op,fields={})=>native.postMessage(JSON.stringify({op,...fields}));
  const page=location.pathname+location.search;
  let active=null;
  function nativeStart(kind,values){
    send('begin',{kind,page,title:document.title.split(' | ')[0],token:bar.dataset.token,speed:kind==='read'?parseFloat(rate.value):1});
    for(let i=0;i<values.length;i+=64)send('parts',{values:values.slice(i,i+64)});
    send('play');
  }
  if(native){
    const audio=main.querySelector('audio[controls]');
    let play,progress,stopAudio,chapter;
    if(audio){
      audio.hidden=true;
      play=document.createElement('button');play.textContent='Play audiobook';
      progress=document.createElement('input');progress.type='range';progress.min=0;progress.max=1000;progress.value=0;
      progress.setAttribute('aria-label','Audiobook position');
      stopAudio=document.createElement('button');stopAudio.textContent='Stop';
      chapter=document.createElement('output');
      audio.after(play,progress,stopAudio,chapter);
      play.onclick=()=>{
        if(active?.kind==='book' && active.page===page){send(active.paused?'resume':'pause');return;}
        const source=new URL(audio.src);
        const first=Number(source.searchParams.get('part')||0);
        const values=[source.pathname+source.search];
        for(const anchor of main.querySelectorAll('nav.pills a')){
          const part=Number(new URL(anchor.href).searchParams.get('part'));
          if(part>first){const next=new URL(source);next.searchParams.set('part',part);values.push(next.pathname+next.search);}
        }
        nativeStart('book',values);
      };
      progress.onchange=()=>send('seek',{value:Math.round(progress.value*active.duration/1000)});
      stopAudio.onclick=()=>send('stop');
    }
    native.onmessage=e=>{
      active=JSON.parse(e.data);
      const reading=active.kind==='read', book=active.kind==='book' && active.page===page;
      if(play){
        play.textContent=book?(active.paused?'Resume':'Pause'):'Play audiobook';
        progress.disabled=stopAudio.disabled=!book;
        if(document.activeElement!==progress)progress.value=book&&active.duration?active.position*1000/active.duration:0;
        chapter.textContent=book?time(active.position/1000)+' / '+time(active.duration/1000):'';
      }
      button('pause').disabled=button('stop').disabled=seek.disabled=!reading;
      button('pause').textContent=reading && active.paused?'Resume':'Pause';
      button('status').textContent=active.error || (reading?(active.paused?'Paused':active.ready?'Reading':'Preparing voice…'):'Emma · Offline voice');
      if(document.activeElement!==seek)seek.value=reading && active.duration?active.position*1000/active.duration:0;
      clock.textContent=reading?time(active.position/1000)+' / '+time(active.duration/1000):'0:00';
    };
    send('status');
    const poll=setInterval(()=>{if(!document.hidden)send('status');},600);
    window.addEventListener('pagehide',()=>clearInterval(poll),{once:true});
  }

  function fetchAudio(n) {
    if (!cache.has(n)) {
      const pending = (async()=>{
        const response=await fetch('/narrate',{method:'POST',signal:request.signal,
          body:new URLSearchParams({token:bar.dataset.token,text:chunks[n]})});
        if(!response.ok) throw Error('Voice unavailable. Check the installed voice package.');
        const wav=await response.blob();
        // The service writes mono 16-bit PCM at the model sample rate.
        const header=new DataView(await wav.slice(0,44).arrayBuffer());
        return {wav,seconds:header.getUint32(40,true)/header.getUint32(28,true)};
      })();
      cache.set(n,pending);
      pending.catch(()=>{if(cache.get(n)===pending)cache.delete(n)});
    }
    return cache.get(n);
  }
  async function playPart(n,fraction=0) {
    const id=++jump, session=track;
    player.onended=null;player.pause(); index=n;loading=true;
    button('status').textContent='Preparing voice…'; display();
    try {
      const sound=await fetchAudio(n);
      if(id!==jump || session!==track)return;
      for(const key of cache.keys())if(key!==n && key!==n+1)cache.delete(key);
      lengths[n]=sound.seconds;
      if(blob)URL.revokeObjectURL(blob);
      blob=URL.createObjectURL(sound.wav);
      player.onloadedmetadata=()=>{
        if(id!==jump)return;
        player.currentTime=Math.min(fraction*sound.seconds,Math.max(0,sound.seconds-.02));
        player.playbackRate=parseFloat(rate.value);loading=false;display();
        button('status').textContent=paused?'Paused':'Reading';
        if(!paused)player.play().catch(()=>{if(id===jump){paused=true;button('status').textContent='Press Resume';display()}});
      };
      player.onerror=()=>{if(id===jump)stop('Could not play generated audio')};
      player.onended=()=>{if(id===jump){if(n+1<chunks.length)playPart(n+1);else stop('Finished')}};
      player.src=blob;
      if(n+1<chunks.length)fetchAudio(n+1).catch(()=>{});
    } catch(error){if(session===track && id===jump)stop(error.message);}
  }
  async function start(getText) {
    stop();const session=track;
    loading=true;button('status').textContent='Opening text…';display();
    try {
      const text=await getText();
      if(session!==track)return;
      chunks=split(text);if(!chunks.length){stop('No readable text on this page');return;}
      if(native){nativeStart("read",chunks);return;}
      lengths=chunks.map(x=>Math.max(.5,x.split(/\s+/).length/2.6));
      playPart(0);
    }catch(error){if(session===track)stop(error.message);}
  }
  player.ontimeupdate=display;
  rate.onchange=()=>{if(native && active?.kind==="read")send("speed",{value:parseFloat(rate.value)});player.playbackRate=parseFloat(rate.value);document.cookie='echo_read_speed='+player.playbackRate+'; Path=/; Max-Age=31536000; SameSite=Strict';};
  seek.onchange=()=>{
    if(native){if(active?.kind==="read")send("seek",{value:Math.round(seek.value*active.duration/1000)});return;}
    if(!chunks.length)return;
    let target=Number(seek.value)/1000*total(), n=0;
    while(n<lengths.length-1 && target>=lengths[n])target-=lengths[n++];
    if(n===index && !loading){player.currentTime=Math.min(target,player.duration);display();}
    else playPart(n,Math.min(1,target/lengths[n]));
  };
  button('pause').onclick=()=>{
    if(native){send(active?.paused?"resume":"pause");return;}
    paused=!paused;
    if(paused)player.pause();else if(!loading)player.play().catch(()=>{paused=true;display()});
    button('status').textContent=paused?'Paused':'Reading';display();
  };
  button('stop').onclick=()=>native?send('stop'):stop('Stopped');
  function selection(doc, frame) {
    const sel=doc.getSelection(), value=sel?.toString().trim();
    if(!value || !sel.rangeCount){if(doc.activeElement!==popup)popup.hidden=true;return;}
    const range=sel.getRangeAt(0);
    if(doc===document && !main.contains(range.commonAncestorContainer))return;
    selected=value;
    const word=value.replace(/^[^\p{L}\p{M}\p{N}]+|[^\p{L}\p{M}\p{N}]+$/gu,'');
    const define=document.querySelector('#define-selection');
    define.hidden=!/^[\p{L}\p{N}][\p{L}\p{M}\p{N}’'‐‑-]{0,159}$/u.test(word);
    if(!define.hidden)define.href='/dictionary?q='+encodeURIComponent(word);

    const box=range.getBoundingClientRect(), parent=frame?.getBoundingClientRect();
    popup.hidden=false;
    popup.style.left=Math.max(8,Math.min(innerWidth-popup.offsetWidth-8,box.left+(parent?.left||0)))+'px';
    popup.style.top=Math.max(8,Math.min(innerHeight-popup.offsetHeight-8,box.bottom+(parent?.top||0)+6))+'px';
  }
  function attach(doc,frame){
    if(!doc)return;
    doc.addEventListener('selectionchange',()=>selection(doc,frame));
    doc.addEventListener('scroll',()=>{
      if(popup.hidden || !doc.getSelection()?.rangeCount)return;
      const range=doc.getSelection().getRangeAt(0).getBoundingClientRect();
      const offset=frame?.getBoundingClientRect().top || 0;
      if(range.bottom+offset<0 || range.top+offset>innerHeight)popup.hidden=true;
      else selection(doc,frame);
    },{passive:true});
  }
  attach(document);
  popup.onpointerdown=e=>e.preventDefault();
  document.querySelector("#speak-selection").onclick=()=>{const passage=selected;popup.hidden=true;start(()=>passage);};
  const frame=main.querySelector('iframe.kit-document');
  if(frame){
    const bind=()=>{try{attach(frame.contentDocument,frame)}catch{}};
    frame.addEventListener('load',bind);bind();
    // WebKit can suppress selectionchange callbacks in script-sandboxed ZIM documents.
    if(frame.hasAttribute('sandbox')){
      let lastNode=null,lastOffset=0,lastFocus=null,lastEnd=0;
      const timer=setInterval(()=>{
        if(document.hidden)return;
        const doc=frame.contentDocument, sel=doc?.getSelection();
        if(!sel)return;
        if(sel.anchorNode===lastNode && sel.anchorOffset===lastOffset &&
           sel.focusNode===lastFocus && sel.focusOffset===lastEnd)return;
        lastNode=sel.anchorNode;lastOffset=sel.anchorOffset;
        lastFocus=sel.focusNode;lastEnd=sel.focusOffset;
        selection(doc,frame);
      },200);
      window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
    }
  }
  const file=main.querySelector('.reader[data-source]')?.dataset.source;
  const isPdf=frame && /\/(kit-file|content-file)\//.test(frame.src);
  const pdf=()=>window.webkit?.messageHandlers?.pdfText?.postMessage(frame.src);
  if(isPdf && window.webkit?.messageHandlers?.pdfText){
    const toggle=document.createElement('button');toggle.textContent='Selectable PDF text';
    const text=document.createElement('pre');text.className='reader';text.hidden=true;
    frame.before(toggle,text);
    toggle.onclick=async()=>{
      if(text.hidden){try{text.textContent=await pdf() || 'No text layer in this PDF.';}catch{text.textContent='Unable to open PDF text.';}}
      frame.hidden=!frame.hidden;text.hidden=!frame.hidden;
      toggle.textContent=text.hidden?'Selectable PDF text':'Show PDF';
    };
  }
  button('all').onclick=()=>start(async()=>{
    if(file){const r=await fetch(file);if(!r.ok)throw Error('Could not read this book');return r.text();}
    if(isPdf){const content=await pdf();if(!content)throw Error('No readable PDF text available');return content;}
    const inner=frame?.contentDocument;
    const article=inner?.querySelector('#mw-content-text,article,main') || inner?.body;
    return article?.innerText || main.querySelector('.reader')?.innerText || main.innerText;
  });
  window.addEventListener('pagehide',()=>stop());
})();
