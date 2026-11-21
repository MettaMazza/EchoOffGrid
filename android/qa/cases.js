(async()=>{
 const get=s=>document.querySelector(s);
 const until=async(f,message)=>{for(let i=0;i<200;i++){if(f())return;await new Promise(r=>setTimeout(r,100));}throw Error(message+' '+get('#case-status').textContent)};
 try {
  const picker=get('#visual-kind');
  for(const [kind,expected] of [['video',['Live video','Camera clip']],['still',['Camera still']],['viewers',['Publisher viewer']],['space',['Satellite image']]]){
    picker.value=kind;picker.dispatchEvent(new Event('change'));
    await until(()=>{const cards=[...document.querySelectorAll('#visual-cards .visual-card')];return cards.length>0 && cards.every(c=>expected.includes(c.querySelector('small').textContent.split(' · ')[0]))},'Filter '+kind);
  }
  const unique='Case QA '+Date.now(), day=new Date().toISOString().slice(0,10);
  const original=JSON.stringify({type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[-2.1,57.15]},properties:{title:unique,time:new Date().toISOString(),detail:'Acceptance fixture, Aberdeen'}}]},null,2);
  const reply=await fetch('/openintel/action',{method:'POST',body:new URLSearchParams({action:'import',region:'aberdeen',token:get('#reader-tools').dataset.token,geojson:original})});
  if(!reply.ok)throw Error(await reply.text());
  get('#case-workspace').open=true;
  const create=get('#case-create');create.elements.title.value=unique;create.requestSubmit();
  await until(()=>Number(get('#case-owner').value)>0,'Create case');
  const owner=get('#case-owner').value, search=get('#case-search');
  search.elements.place.value=unique;search.elements.start.value=day;search.elements.end.value=day;search.requestSubmit();
  await until(()=>get('#case-results h4')?.textContent===unique,'Search dated local observation');
  get('#case-results button').click();await until(()=>get('#case-exhibits').textContent.includes(unique),'Save original');
  search.elements.place.value='Lend-Lease';search.elements.start.value='';search.elements.end.value='';search.requestSubmit();
  await until(()=>get('#case-results h4')?.textContent.includes('Lend-Lease'),'Search document');
  get('#case-results button').click();await until(()=>get('#case-exhibits').children.length===2,'Save document');
  get('#case-results button').click();await until(()=>!get('#case-results button').disabled,'Retry save');
  get('#case-owner').value='0';get('#case-owner').dispatchEvent(new Event('change'));
  await until(()=>!get('#case-exhibits').children.length,'Switch case');
  get('#case-owner').value=owner;get('#case-owner').dispatchEvent(new Event('change'));
  await until(()=>get('#case-exhibits').children.length===2,'Reopen saved case');
  search.elements.place.value=unique;search.elements.start.value='2000-01-01';search.elements.end.value='2000-01-01';search.requestSubmit();
  await until(()=>get('#case-status').textContent.includes('No retained records'),'Date exclusion');
  const coverage=get('#case-coverage');
  coverage.elements.start.value=day+'T00:00';
  coverage.elements.end.value=day+'T23:59';
  coverage.requestSubmit();
  await until(()=>get('#case-coverage-results summary') && get('#case-coverage-results li'),'Source coverage');
  const relationship=get('#case-relationship');
  relationship.closest('details').open=true;
  for(const [key,value] of Object.entries({subject:'Case QA',predicate:'reviewed',object:unique,assessment:'Uncertain',passage:'Synthetic observation for acceptance testing.'}))relationship.elements[key].value=value;
  relationship.elements.ref.selectedIndex=1;
  relationship.requestSubmit();
  await until(()=>get('#case-relationships').textContent.includes('Uncertain'),'Relationship review');
  const finding=get('#case-finding'), links=finding.querySelectorAll('select');
  links[0].value='supports'; links[1].value='contradicts';
  finding.elements.statement.value='Synthetic test finding';
  finding.elements.unknowns.value='Independent corroboration';
  finding.requestSubmit();
  await until(()=>['supports','contradicts','Independent corroboration'].every(t=>get('#case-findings').textContent.includes(t)),'Finding with exhibits');
  await until(()=>['Retrieved','Finding recorded','Relationship reviewed'].every(t=>get('#case-timeline').textContent.includes(t)),'Case timeline');
  window.caseQA={owner,original};get('#case-export').click();
 } catch(e){window.caseQA={error:String(e)}}
})();
