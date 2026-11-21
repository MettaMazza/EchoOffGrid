(async()=>{
  const el=id=>document.getElementById(id);
  const wait=async(test,label)=>{
    for(let i=0;i<600;i++){if(test())return;await new Promise(resolve=>setTimeout(resolve,150));}
    throw Error(label+' · '+el('case-places-status').textContent+' · '+el('compare-frames').innerText);
  };
  try {
    if(el('intel-region').value!=='aberdeen')throw Error('Expected Aberdeen');
    el('case-workspace').open=true;
    const places=el('case-places');
    places.elements.clue.value='lighthouse';
    places.requestSubmit();
    await wait(()=>/matches|Download landmarks/.test(el('case-places-status').textContent),'Read extract');
    if(!el('case-places-results').children.length)el('case-places-fetch').click();
    await wait(()=>el('case-places-results').textContent.includes('North Breakwater'),'Harbour landmark');
    const compare=el('compare-dates');
    el('compare-imagery').open=true;
    compare.elements.earlier.value='2024-06-01';
    compare.elements.later.value='2024-06-02';
    const frames=el('compare-frames');
    for(let pass=0;pass<2;pass++){
      compare.requestSubmit();
      await wait(()=>frames.children.length===2 && Array.from(frames.children).every(f=>f.querySelector('button,img')),'Read dated frames');
      if(pass===0)for(const button of frames.querySelectorAll('button'))button.click();
      await wait(()=>Array.from(frames.querySelectorAll('img')).filter(img=>img.complete && img.naturalWidth===768).length===2,'Open both saved images');
    }
    window.geographyQA={landmarks:el('case-places-results').children.length,frames:Array.from(frames.querySelectorAll('figure'),f=>[f.querySelector('h4').textContent,f.querySelector('img').naturalWidth,f.querySelector('p').textContent])};
  }catch(error){window.geographyQA={error:String(error)};}
})();
