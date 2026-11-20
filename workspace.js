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
  const savedMotion = document.cookie.match(/(?:^|; )echo_pause_motion=(yes|no)(?:;|$)/);
  let paused = savedMotion ? savedMotion[1] === 'yes' : reduce.matches || sessionStorage.getItem('pauseMotion') === 'yes';
  const motion = document.querySelector('#motion');
  function showMotion() {
    if (motion) {
      motion.textContent = paused ? 'Play rotation' : 'Pause rotation';
      motion.setAttribute('aria-pressed', String(paused));
    }
  }
  if (motion) motion.onclick = () => {
    paused = !paused;
    document.cookie='echo_pause_motion='+(paused?'yes':'no')+'; Path=/; Max-Age=31536000; SameSite=Strict';
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
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'drawer-trigger';
  trigger.setAttribute('aria-label', 'Open navigation');
  trigger.setAttribute('aria-controls', 'section-drawer');
  trigger.setAttribute('aria-haspopup', 'dialog');
  trigger.setAttribute('aria-expanded', 'false');
  header.prepend(trigger);

  const drawer = document.createElement('dialog');
  drawer.id = 'section-drawer';
  drawer.setAttribute('aria-labelledby', 'drawer-title');
  drawer.innerHTML = '<div class="drawer-heading"><strong id="drawer-title">Navigation</strong><button type="button" aria-label="Close navigation">×</button></div>';
  const navigation = header.querySelector('nav').cloneNode(true);
  drawer.append(navigation);
  document.body.append(drawer);

  trigger.onclick = () => {
    drawer.showModal();
    trigger.setAttribute('aria-expanded', 'true');
  };
  drawer.querySelector('button').onclick = () => drawer.close();
  drawer.addEventListener('click', event => {
    if (event.target.closest('a') || (event.target === drawer && event.clientX >= drawer.getBoundingClientRect().right)) drawer.close();
  });
  drawer.addEventListener('close', () => {
    trigger.setAttribute('aria-expanded', 'false');
    if (trigger.offsetWidth) trigger.focus({preventScroll:true});
  });
  const compact = matchMedia('(max-width:699px), (pointer:coarse) and (max-height:600px)');
  compact.addEventListener('change', () => { if (!compact.matches && drawer.open) drawer.close(); });
  window.addEventListener('pagehide', () => { if (drawer.open) drawer.close(); });
  const toggle = header.querySelector('.reader-toggle');
  toggle.onclick = () => {
    const open = document.body.classList.toggle('reader-open');
    toggle.setAttribute('aria-expanded', String(open));
  };
  const shortcut = document.createElement('a');
  shortcut.href = navigation.querySelector('a[href="/echolite"]').href;
  shortcut.className = 'echo-shortcut';
  shortcut.draggable = false;
  shortcut.setAttribute('aria-label', 'Open EchoLite');
  shortcut.title = 'Open EchoLite';
  shortcut.innerHTML = '<svg aria-hidden="true" viewBox="940 136 168 168" fill="none" stroke="currentColor" stroke-linecap="round"><path d="M1060 167a64 64 0 1 0 0 106" stroke-width="12"/><path d="M1046 194a32 32 0 1 0 0 52" stroke-width="8"/><circle cx="1024" cy="220" r="7" fill="currentColor" stroke="none"/></svg>';
  document.body.append(shortcut);

  const clamp = value => Math.min(1, Math.max(0, value));
  const saved = document.cookie.match(/(?:^|; )echo_shortcut=(0|1|0\.\d+),(0|1|0\.\d+)(?:;|$)/);
  let position = saved ? [Number(saved[1]), Number(saved[2])] : [1, .77];
  let drag, suppressClick = false;
  function travel() {
    return [Math.max(1, document.documentElement.clientWidth - shortcut.offsetWidth - 16),
            Math.max(1, window.innerHeight - shortcut.offsetHeight - 16)];
  }
  function place() {
    if (!shortcut.offsetWidth) return;
    const [width,height] = travel();
    shortcut.style.left = (8 + position[0] * width) + 'px';
    shortcut.style.top = (8 + position[1] * height) + 'px';
  }
  shortcut.addEventListener('pointerdown', e => {
    if (!e.isPrimary || e.button !== 0) return;
    suppressClick = false;
    drag = {id:e.pointerId, x:e.clientX, y:e.clientY, start:position.slice(), moved:false};
    shortcut.setPointerCapture(e.pointerId);
  });
  shortcut.addEventListener('pointermove', e => {
    if (!drag || e.pointerId !== drag.id) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx,dy) < 7) return;
    drag.moved = true;
    const [width,height] = travel();
    position = [clamp(drag.start[0] + dx/width), clamp(drag.start[1] + dy/height)];
    place();
  });
  function finishDrag(e) {
    if (!drag || e.pointerId !== drag.id) return;
    suppressClick = drag.moved;
    if (drag.moved) document.cookie = 'echo_shortcut=' + position.map(n=>Number(n.toFixed(4))).join(',') + '; Path=/; Max-Age=31536000; SameSite=Strict';
    drag = null;
  }
  shortcut.addEventListener('pointerup', finishDrag);
  shortcut.addEventListener('lostpointercapture', finishDrag);
  shortcut.addEventListener('click', e => { if (suppressClick && e.detail !== 0) e.preventDefault(); suppressClick = false; });
  window.addEventListener('resize', place);
  document.body.classList.add('mobile-ready');
  place();
})();

const mainVideo = document.querySelector('main video[controls]');
if (mainVideo) {
  const playerLink = document.querySelector('main a[href^="/player/"]');
  if(playerLink && navigator.userAgent.includes('EchoOffGrid/Android')){
    const small=document.createElement('a');small.href=playerLink.href;small.textContent='Picture in picture';
    small.className='button';
    small.addEventListener('click',()=>{
      const url=new URL(playerLink.href);url.searchParams.set('pip','1');
      url.searchParams.set('at',Math.round(mainVideo.currentTime*1000));small.href=url.href;mainVideo.pause();
    });
    playerLink.after(' ',small);
  }
  const offerNativePlayer = () => {
    if (!playerLink || !mainVideo.error) return;
    mainVideo.hidden = true;
    playerLink.classList.add('button');
    playerLink.textContent = 'Play this video in the built-in player';
  };
  mainVideo.addEventListener('error', offerNativePlayer);
  offerNativePlayer();
}
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

// Rewrite actual hrefs so new tabs and keyboard activation follow the same protected route.
function protectWebLinks(doc) {
  function rewrite(anchor) {
    const raw = anchor.getAttribute('href');
    if (!raw) return;
    let target;
    try { target = new URL(raw, doc.baseURI); } catch { return; }
    if (!['http:', 'https:'].includes(target.protocol) || target.origin === location.origin) return;
    anchor.href = location.origin + '/private-browser?' + new URLSearchParams({to: target.href});
    anchor.removeAttribute('target');
    anchor.removeAttribute('download');
  }
  function scan(root) {
    if (root.matches?.('a[href]')) rewrite(root);
    root.querySelectorAll?.('a[href]').forEach(rewrite);
  }
  scan(doc);
  new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'attributes') rewrite(record.target);
      else record.addedNodes.forEach(scan);
    }
  }).observe(doc.documentElement, {subtree:true,childList:true,attributes:true,attributeFilter:['href']});
  doc.addEventListener('click', event => {
    const anchor=event.target.closest?.('a[href]');
    if (!anchor) return;
    rewrite(anchor);
    if (doc !== document && anchor.origin === location.origin && anchor.pathname === '/private-browser') {
      event.preventDefault();
      location.assign(anchor.href);
    }
  },true);
}
protectWebLinks(document);
function protectFrame(frame) {
  try { if (frame.contentDocument?.documentElement) protectWebLinks(frame.contentDocument); } catch {}
}
document.querySelectorAll('iframe').forEach(protectFrame);
document.addEventListener('load',e=>{if(e.target.tagName==='IFRAME')protectFrame(e.target);},true);

const exitSelect=document.querySelector('.private-browser-controls [name=country]');
const savedExit=document.cookie.match(/(?:^|; )echo_exit=([a-z]{0,2})(?:;|$)/);
if(exitSelect){
  if(savedExit && [...exitSelect.options].some(o=>o.value===savedExit[1]))exitSelect.value=savedExit[1];
  exitSelect.addEventListener('change',()=>{document.cookie='echo_exit='+exitSelect.value+'; Path=/; Max-Age=31536000; SameSite=Strict';});
}
const phoneVPN = navigator.userAgent.includes('EchoOffGrid/Android');
const nativePrivate = phoneVPN || navigator.userAgent.includes('EchoOffGrid/Mac');
async function phoneState() {
  const response=await fetch('/phone-vpn-status',{cache:'no-store'});
  if (!response.ok) throw Error('VPN status unavailable');
  return response.json();
}
if (phoneVPN) {
  const toggle=document.createElement('a');
  toggle.className='phone-vpn-toggle';
  toggle.setAttribute('role','switch');
  document.querySelector('.workstation-header')?.append(toggle);
  async function updateToggle() {
    try {
      const {enabled,status}=await phoneState();
      const params=new URLSearchParams({action:enabled?'off':'on'});
      const field=document.querySelector('[name=country]');
      if(field) params.set('country',field.value);
      toggle.href='/phone-vpn?'+params;
      toggle.textContent='VPN '+(enabled ? (status==='Connected over Tor'?'on':'…') : 'off');
      toggle.title='Phone VPN · '+status;
      toggle.setAttribute('aria-label',toggle.title);
      toggle.setAttribute('aria-checked',String(enabled));
    } catch { toggle.removeAttribute('href'); toggle.textContent='Phone VPN unavailable'; }
  }
  updateToggle();
  document.querySelector('[name=country]')?.addEventListener('change',updateToggle);
  const timer=setInterval(updateToggle,1500);
  window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
}

const privateStatus=document.querySelector('#private-status');
if (privateStatus) {
  const link=document.querySelector('#native-browser-launch');
  const destination=link.dataset.destination;
  let launched=false, busy=false, started=false;
  const reader=document.getElementById('private-links');
  function openReader(url) {
    const field=document.createElement('input');
    field.type='hidden';field.name='url';field.value=url;
    reader.append(field);reader.submit();
  }
  link.addEventListener('click',e=>{
    if(link.getAttribute('aria-disabled')==='true') e.preventDefault();
    else if(!nativePrivate){e.preventDefault();openReader(destination || 'https://duckduckgo.com/');}
  });
  async function refresh() {
    if(busy)return;
    busy=true;
    try {
      const phone=phoneVPN ? await phoneState() : {enabled:false};
      if(destination && !started && !phone.enabled) {
        const response=await fetch('/private-browser',{method:'POST',body:new URLSearchParams({
          token:reader.elements.token.value,action:'ensure',country:exitSelect.value
        })});
        if(response.status!==204)throw Error();
        started=true;
      }
      const response=await fetch('/private-status'+(phone.enabled?'?phone=1':''),{cache:'no-store'});
      if(!response.ok)throw Error();
      const session=await response.json();
      const ready=phone.enabled ? phone.status==='Connected over Tor' : session.ready;
      privateStatus.textContent=phone.enabled ? 'Phone VPN · '+phone.status : session.status;
      link.setAttribute('aria-disabled',String(!ready));
      if(!ready){link.removeAttribute('href');return;}
      link.href='/private-open?'+new URLSearchParams({port:session.port,url:destination || 'https://duckduckgo.com/'});
      if(destination && !launched) {
        launched=true;
        if(nativePrivate) location.assign(link.href); else openReader(destination);
      }
    } catch {
      privateStatus.textContent='Could not establish a protected connection.';
      link.setAttribute('aria-disabled','true');link.removeAttribute('href');
    } finally {busy=false;}
  }
  refresh();
  const timer=setInterval(refresh,1500);
  window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
}

document.querySelector('.workstation-back')?.addEventListener('click',()=>{
  if(history.length>1)history.back();else if(location.pathname!=='/')location.assign('/');
});
document.addEventListener('error',e=>{if(e.target instanceof HTMLImageElement && e.target.closest('.publisher-art'))e.target.closest('.publisher-art').classList.add('unavailable');},true);

(() => {
  const main = document.querySelector('main');
  if (!main?.querySelector('.h-atlas')) return;
  let pending;
  function position(initial = false) {
    const entries = main.querySelector('#history-entries');
    if (main.querySelector('.h-atlas').dataset.showEntries === '1') {
      entries.focus({preventScroll:true});
      entries.scrollIntoView({block:'start'});
    } else if (!initial) {
      main.querySelector('.h-atlas').scrollIntoView({block:'start'});
    }
  }
  async function update(url) {
    pending?.abort();
    const request = new AbortController();
    pending = request;
    main.setAttribute('aria-busy','true');
    try {
      const response = await fetch(url,{signal:request.signal});
      if (!response.ok) throw Error('Timeline unavailable');
      const next = new DOMParser().parseFromString(await response.text(),'text/html').querySelector('main');
      if (!next?.querySelector('.h-atlas')) throw Error('Timeline unavailable');
      if (request.signal.aborted) return;
      document.querySelector('#read-stop:not(:disabled)')?.click();
      history.replaceState(history.state,'',url);
      main.replaceChildren(...next.childNodes);
      position();
    } catch (error) {
      if (!request.signal.aborted) location.replace(url);
    } finally {
      if (pending === request) main.removeAttribute('aria-busy');
    }
  }
  main.addEventListener('click',event=>{
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (url.origin!==location.origin || url.pathname!=='/history' || url.searchParams.has('read')) return;
    event.preventDefault();
    update(url);
  });
  main.addEventListener('submit',event=>{
    if (!event.target.matches('form.h-search')) return;
    event.preventDefault();
    const url = new URL('/history',location.origin);
    url.search = new URLSearchParams(new FormData(event.target));
    update(url);
  });
  main.addEventListener('wheel',event=>{
    const rail = event.target.closest('.h-rail');
    if (!rail || event.ctrlKey || event.deltaX || !event.deltaY) return;
    const max = rail.scrollWidth-rail.clientWidth;
    if ((event.deltaY>0 && rail.scrollLeft<max-1) || (event.deltaY<0 && rail.scrollLeft>1)) {
      event.preventDefault();
      rail.scrollLeft+=event.deltaY*(event.deltaMode===1?16:1);
    }
  },{passive:false});
  window.addEventListener('pagehide',()=>pending?.abort());
  position(true);
})();

(() => {
  const status = document.querySelector('#wiki-progress[data-running="1"]');
  if (!status) return;
  async function update() {
    try {
      const response = await fetch('/wiki-progress', {cache:'no-store'});
      if (response.ok) {
        const progress = await response.json();
        status.textContent = progress.status;
        if (!progress.active) { location.reload(); return; }
      }
    } catch (_) {}
    setTimeout(update, 5000);
  }
  setTimeout(update, 5000);
})();
