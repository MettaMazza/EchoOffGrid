(() => {
  const wikiFrame = document.querySelector('.wiki-frame');
  if (wikiFrame) {
    const reveal = () => {
      const doc = wikiFrame.contentDocument;
      if (!doc || doc.URL === 'about:blank' || doc.readyState !== 'complete') return;
      wikiFrame.classList.add('ready');
      doc.defaultView.addEventListener('pagehide', () => wikiFrame.classList.remove('ready'), {once:true});
      doc.defaultView.addEventListener('pageshow', () => wikiFrame.classList.add('ready'), {once:true});
    };
    wikiFrame.addEventListener('load', reveal);
    reveal();
  }
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reduce.matches || sessionStorage.getItem('pauseMotion') === 'yes';
  const motion = document.querySelector('#motion');
  function showMotion() {
    if (motion) {
      motion.textContent = paused ? 'Play rotation' : 'Pause rotation';
      motion.setAttribute('aria-pressed', String(paused));
    }
  }
  if (motion) motion.onclick = () => {
    paused = !paused;
    sessionStorage.setItem('pauseMotion', paused ? 'yes' : 'no');
    showMotion();
  };
  showMotion();
  const category=new URLSearchParams(location.search).get('category');
  if(category){
    const groups=[...document.querySelectorAll('.source-group')];
    const selected=groups.find(g=>g.dataset.category===category);
    if(selected){groups.forEach(g=>g.open=g===selected);selected.scrollIntoView({block:'center'});}
  }
  const onLoad = document.querySelectorAll('[data-on-load]');
  if (onLoad.length) {
    const visit = Number(sessionStorage.getItem('homeVisit') || 0);
    for (const group of onLoad) {
      const cards = [...group.children];
      const offset = visit % cards.length;
      for (const card of cards.slice(0, offset)) group.append(card);
    }
    sessionStorage.setItem('homeVisit', String(visit + 1));
  }
  function updateRail(rail) {
    const max = rail.scrollWidth - rail.clientWidth;
    rail.previousElementSibling.disabled = rail.scrollLeft <= 2;
    rail.nextElementSibling.disabled = rail.scrollLeft >= max - 2;
  }
  function moveRail(rail, direction, wrap=false) {
    const last = rail.scrollWidth - rail.clientWidth;
    const target = wrap && rail.scrollLeft >= last - 2 ? 0 :
      rail.scrollLeft + direction * rail.clientWidth * .9;
    rail.scrollTo({left: target, behavior: reduce.matches ? 'instant' : 'smooth'});
  }
  function setupRails() {
    document.querySelectorAll('.rail').forEach(rail => {
      if (rail.dataset.ready) return;
      rail.dataset.ready = 'true';
      rail.previousElementSibling.onclick = () => moveRail(rail, -1);
      rail.nextElementSibling.onclick = () => moveRail(rail, 1);
      rail.addEventListener('scroll', () => updateRail(rail), {passive:true});
      rail.addEventListener('keydown', event => {
        if (event.target !== rail || !['ArrowLeft','ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        moveRail(rail, event.key === 'ArrowLeft' ? -1 : 1);
      });
      updateRail(rail);
    });
  }
  const refreshRails = () => document.querySelectorAll('.rail').forEach(updateRail);
  setupRails();
  document.addEventListener('railschanged', setupRails);
  window.addEventListener('resize', refreshRails);
  document.querySelector('#shelf-search')?.addEventListener('input', refreshRails);
  const cycle=document.querySelector('#cycle');
  if (cycle) {
    const nextSources = manual => {
      const rail=document.querySelector('#recent-cards');
      if (rail && (manual || !rail.parentElement.matches(':hover,:focus-within'))) moveRail(rail,1,true);
    };
    cycle.onclick=()=>nextSources(true);
    setInterval(()=>{if(!paused && !document.hidden) nextSources(false);},8500);
  }

  let active;
  function endPreview() {
    if (!active) return;
    const video=active; active=null;
    video.pause();video.removeAttribute('src');video.load();video.remove();
  }
  function preview(el) {
    if (!el || reduce.matches || el.contains(active)) return;
    endPreview();
    const video=document.createElement('video');
    video.muted=true;video.playsInline=true; video.setAttribute('aria-hidden','true');
    video.addEventListener('error', endPreview,{once:true});
    video.onended=endPreview;
    const cover = el.querySelector('img');
    if (cover) video.poster = cover.currentSrc || cover.src;
    video.style.visibility='hidden';
    const reveal = () => { if (active === video) video.style.visibility='visible'; };
    if ('requestVideoFrameCallback' in video) video.requestVideoFrameCallback(reveal);
    else video.addEventListener('playing',reveal,{once:true});
    video.src=el.dataset.clip; active=video; el.append(video);
    video.play().catch(()=>{if(active===video) endPreview()});
    setTimeout(()=>{if(active===video)endPreview()},4500);
  }
  let touchStart;
  function cancelTouch() {
    if (touchStart) clearTimeout(touchStart.timer);
    touchStart = null;
  }
  document.addEventListener('pointerdown', e => {
    if (e.pointerType !== 'touch') return;
    cancelTouch();
    const clip = e.target.closest('.item')?.querySelector('[data-clip]');
    if (clip) touchStart = {x:e.clientX,y:e.clientY,id:e.pointerId,
      timer:setTimeout(() => preview(clip),260)};
  }, {passive:true});
  document.addEventListener('pointermove', e => {
    if (touchStart && e.pointerId===touchStart.id &&
        Math.hypot(e.clientX-touchStart.x,e.clientY-touchStart.y)>8) {
      cancelTouch(); endPreview();
    }
  }, {passive:true});
  for (const event of ['pointerup','pointercancel']) document.addEventListener(event, e => {
    if (e.pointerType==='touch') {cancelTouch(); if(event==='pointercancel') endPreview();}
  }, {passive:true});
  ['pointerover','focusin'].forEach(name=>document.addEventListener(name,e=>{
    if (e.pointerType === 'touch' || (e.type === 'focusin' && !e.target.matches(':focus-visible'))) return;
    const tile=e.target.closest('.item');
    if(tile && !tile.contains(e.relatedTarget)) preview(tile.querySelector('[data-clip]'));
  }));
  ['pointerout','focusout'].forEach(name=>document.addEventListener(name,e=>{
    const tile=e.target.closest('.item');
    if(tile && active && tile.contains(active) && !tile.contains(e.relatedTarget))endPreview();
  }));
  const zip = document.querySelector('#inspect-zip');
  if (zip) {
    const lib=document.createElement('script');lib.src='/integrations/jszip.js';
    document.head.append(lib);
    const summary=document.querySelector('#zip-summary'), list=document.querySelector('#zip-entries');
    zip.addEventListener('change',async()=>{
      const file=zip.files[0]; if(!file)return;
      list.replaceChildren(); summary.textContent='Opening archive…';
      try {
        if(file.size>128*1024*1024)throw Error('Choose an archive smaller than 128 MB.');
        const archive=await JSZip.loadAsync(file);
        const files=Object.values(archive.files).filter(item=>!item.dir);
        for(const item of files.slice(0,2000)){
          const row=document.createElement('li'); row.textContent=item.name;list.append(row);
        }
        summary.textContent=file.name+' · '+files.length+' files'+(files.length>2000?' · showing first 2,000':'');
      }catch(error){summary.textContent='Could not open ZIP. '+error.message;}
    });
  }
})();

(() => {
  const header = document.querySelector('.workstation-header');
  if (!header) return;
  const links = [...header.querySelectorAll('nav a')];
  const primary = new Set(['Home', 'Library', 'News', 'EchoLite']);
  const dock = document.createElement('nav');
  dock.className = 'mobile-dock';
  dock.setAttribute('aria-label', 'Main sections');
  const panel = document.createElement('dialog');
  panel.className = 'mobile-menu';
  panel.setAttribute('aria-label', 'More sections');
  panel.innerHTML = '<div><strong>More sections</strong><button aria-label="Close menu">Close</button></div>';
  for (const link of links) {
    const copy = link.cloneNode(true);
    copy.dataset.icon = copy.textContent;
    (primary.has(copy.textContent) ? dock : panel).append(copy);
  }
  const more = document.createElement('button');
  more.type = 'button';
  more.dataset.icon = 'More';
  more.textContent = 'More';
  more.setAttribute('aria-haspopup', 'dialog');
  if (panel.querySelector('[aria-current=page]')) more.className = 'current';
  more.onclick = () => panel.showModal();
  panel.querySelector('button').onclick = () => panel.close();
  panel.onclick = e => { if (e.target === panel && e.clientY < panel.getBoundingClientRect().top) panel.close(); };
  dock.append(more);
  document.body.append(dock, panel);
  const toggle = header.querySelector('.reader-toggle');
  toggle.onclick = () => {
    const open = document.body.classList.toggle('reader-open');
    toggle.setAttribute('aria-expanded', String(open));
  };
  document.body.classList.add('mobile-ready');
})();

const mainVideo = document.querySelector('main video[controls]');
const autoplay = document.querySelector('#video-autoplay');
if (mainVideo && autoplay) {
  autoplay.checked = document.cookie.split('; ').includes('echo_autoplay=1');
  autoplay.addEventListener('change', () => {
    document.cookie = 'echo_autoplay=' + Number(autoplay.checked) + '; Path=/; Max-Age=31536000; SameSite=Strict';
  });
  mainVideo.addEventListener('ended', () => {
    const next = autoplay.closest('.up-next').dataset.next;
    if (autoplay.checked && next) location.assign(next + '?autoplay=1');
  });
}
if (mainVideo && new URLSearchParams(location.search).get('autoplay') === '1') {
  const clean = new URL(location.href);
  clean.searchParams.delete('autoplay');
  history.replaceState(history.state, '', clean);
  if (autoplay?.checked) mainVideo.play().catch(() => {});
}

const importForm=document.querySelector('.personal-import');
if(importForm) importForm.onsubmit=async event=>{
  event.preventDefault();
  const {files}=importForm.elements, button=importForm.querySelector('button'), status=importForm.querySelector('output');
  const headers={'X-Library-Token':importForm.dataset.token};
  let count=0;button.disabled=true;
  try{
    for(const file of files.files){
      status.textContent='Importing '+file.name+'…';
      const result=await fetch(importForm.action,{method:'POST',headers:{...headers,'X-Filename':encodeURIComponent(file.name)},body:file});
      if(!result.ok)throw Error('Could not import '+file.name);
      const key=await result.text();count++;
      if(file.name.toLowerCase().endsWith('.app.zip') && window.webkit?.messageHandlers?.importedFile){
        await window.webkit.messageHandlers.importedFile.postMessage({id:key,name:file.name});
      }
      if(importForm.dataset.android==="1") await fetch('/native-metadata/'+key,{method:'POST',headers:{'X-Echo-Library':'import'}});
    }
    status.textContent=count+' imported. Reload to see your shelf.';files.value='';window.location.reload();
  }catch(error){status.textContent=count+' imported. '+error.message;}finally{button.disabled=false;}
};
document.querySelector('#population-filter')?.addEventListener('input',event=>{
  const text=event.target.value.toLocaleLowerCase();
  document.querySelectorAll('#population-records tbody tr').forEach(row=>{
    row.hidden=!row.cells[0].textContent.toLocaleLowerCase().includes(text);
  });
});

const privateStatus = document.querySelector('#private-status');
if (privateStatus) {
  const pollPrivateStatus = async () => {
    try {
      const response = await fetch('/private-status', {cache:'no-store'});
      if (!response.ok) throw Error();
      const {status, ready, port} = await response.json();
      privateStatus.textContent = status;
      const link=document.querySelector('#native-browser-launch');link.href=ready?'/private-open?port='+port:'/private-open';link.setAttribute('aria-disabled',String(!ready));
    } catch {
      privateStatus.textContent = 'Connection unavailable';
      document.querySelector('#native-browser-launch').setAttribute('aria-disabled','true');
    }
  };
  pollPrivateStatus();
  const timer = setInterval(pollPrivateStatus, 1500);
  window.addEventListener('pagehide', () => clearInterval(timer), {once:true});
}

document.querySelector('.workstation-back')?.addEventListener('click',()=>{
  if(history.length>1)history.back();else if(location.pathname!=='/')location.assign('/');
});
document.addEventListener('error',e=>{if(e.target instanceof HTMLImageElement && e.target.closest('.publisher-art'))e.target.closest('.publisher-art').classList.add('unavailable');},true);

const historyRail=document.querySelector('.h-rail');
if(historyRail)historyRail.addEventListener('wheel',event=>{
  if(event.ctrlKey || event.deltaX || !event.deltaY)return;
  const max=historyRail.scrollWidth-historyRail.clientWidth;
  if((event.deltaY>0 && historyRail.scrollLeft<max-1)||(event.deltaY<0 && historyRail.scrollLeft>1)){
    event.preventDefault();
    historyRail.scrollLeft+=event.deltaY*(event.deltaMode===1?16:1);
  }
},{passive:false});
