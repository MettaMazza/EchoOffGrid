// The host reinjects this script after each navigation. Each run uses its own disposable collection.
(async()=>{
  if(window.seriesCheckStarted)return;
  window.seriesCheckStarted=true;
  const key=window.qaSeriesKey, base='/content/'+key, state=sessionStorage;
  const wait=async(predicate,message)=>{
    for(let i=0;i<180;i++){if(predicate())return;await new Promise(r=>setTimeout(r,80));}
    throw Error(message);
  };
  const stage=Number(state.seriesStep||0), video=document.querySelector('main video');
  const go=(step,url)=>{state.seriesStep=step;location.assign(url)};
  const expect=(v,msg)=>{if(!v)throw Error(msg)};
  try{
    if(stage===0){
      const toggle=document.querySelector('#video-autoplay');
      expect(document.querySelectorAll('.episode-grid a').length===3,'missing ordered grid');
      if(!toggle.checked)toggle.click();
      go(1,base);
    }else if(stage===1){
      expect(location.search.includes('part=0'),'did not start episode one');
      await wait(()=>video?.currentTime>0.1 && !video.paused,'episode one did not play');
      const parts=[...document.querySelectorAll('.up-next .item')].map(a=>new URL(a.href).searchParams.get('part'));
      expect(parts.join(',')==='1,2','incorrect Up Next order '+parts);
      state.seriesStep=2;video.currentTime=video.duration-.25;
    }else if(stage===2){
      expect(location.search.includes('part=1'),'did not advance to episode two');
      await wait(()=>video?.currentTime>.15 && !video.paused,'episode two did not play');
      video.currentTime=video.duration*.45;
      await wait(()=>!video.seeking,'seek failed');video.pause();
      state.seriesPosition=video.currentTime;
      const positions=async()=>new DOMParser().parseFromString(await (await fetch(base+'?episodes=1')).text(),'text/html');
      for(let n=0;n<60;n++){const doc=await positions();if(doc.querySelectorAll('.episode-progress').length>=2)break;await new Promise(r=>setTimeout(r,100));}
      go(3,base+'?episodes=1');
    }else if(stage===3){
      const meters=[...document.querySelectorAll('.episode-grid progress')].map(p=>p.value);
      expect(meters.length===2 && meters[0]===100 && meters[1]>=35 && meters[1]<=65,'wrong thumbnail progress '+meters);
      go(4,base);
    }else if(stage===4){
      expect(location.search.includes('part=1'),'did not resume latest episode');
      await wait(()=>video?.currentTime>=Number(state.seriesPosition)-.1 && !video.paused,'resume time incorrect');
      const toggle=document.querySelector('#video-autoplay');toggle.click();
      video.currentTime=video.duration-.2;
      await wait(()=>video.ended,'episode did not end');
      await new Promise(r=>setTimeout(r,400));
      expect(location.search.includes('part=1'),'advanced with autoplay off');
      window.seriesPlaybackProof='PASS · ordered queue, real playback, automatic advance, completion and partial progress, resume, autoplay off';
    }
  }catch(error){window.seriesPlaybackProof='FAIL '+stage+' '+String(error);}
})();
