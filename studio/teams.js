(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const browserEdition = window.BROWSER_EDITION === true;
  const defaults = {count: 5, mode: 'hybrid', template: 'original', language: 'en', audience: '', min_year: null, model: 'offline'};
  const suggestions = [
    ['book', '', 'Antimicrobial stewardship', 'Prepare a briefing for veterinary teams.', 'Create a briefing for veterinary teams on antimicrobial stewardship in food-producing animals.'],
    ['leaf', 'green', 'Poultry & prevention', 'Explore responsible use on farms.', 'Build a farmer training deck about poultry, disease prevention and responsible antimicrobial use.'],
    ['globe', 'orange', 'One Health coordination', 'Introduce cross-sector action on AMR.', 'Prepare an introductory One Health briefing on coordinating action against antimicrobial resistance.']
  ];
  let settings = {...defaults};
  let session = {};
  let current = {};
  let transcript = [];
  let busy = false;
  let custom = false;
  let requiredLogin = false;
  let toastTimer;
  function el(tag, content, cls) {
    const result = document.createElement(tag);
    if (content !== undefined && content !== null) result.textContent = String(content);
    if (cls) result.className = cls;
    return result;
  }
  function icon(id) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    const use = document.createElementNS('http://www.w3.org/2000/svg','use');
    svg.setAttribute('aria-hidden','true');
    use.setAttribute('href', '#i-' + id);
    svg.append(use);
    return svg;
  }
  function avatar() {
    const span = el('span', null, 'ppt-icon small'); span.setAttribute('aria-hidden','true');
    span.append(el('i'), el('b','P'));
    return span;
  }
  function button(label, callback, cls = 'regular-btn', symbol) {
    const btn = el('button', null, cls);
    btn.type = 'button';
    if (symbol) btn.append(icon(symbol));
    btn.append(document.createTextNode(label));
    btn.onclick = callback;
    return btn;
  }
  function info(msg) {
    $('toast').textContent = msg;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $('toast').textContent = ''; }, 4500);
  }
  function formatted(value) {
    if (Array.isArray(value)) return value.map(formatted).filter(Boolean).join('\n');
    if (value && typeof value === 'object') return Object.values(value).map(formatted).filter(Boolean).join(' · ');
    return value == null ? '' : String(value);
  }
  function safeLink(raw, file = false) {
    if (typeof raw !== 'string' || !raw) return '';
    try {
      const url = new URL(raw, location.href);
      if (file) {
        if (browserEdition && url.protocol === 'blob:' && url.origin === location.origin) return url.href;
        if (url.origin === location.origin && (url.protocol === 'http:' || url.protocol === 'https:') && url.pathname.startsWith('/api/files/')) return url.href;
        return '';
      }
      return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch { return ''; }
  }
  async function api(method, path, body) {
    if (browserEdition) return window.browserAPI(method, path, body);
    const response = await fetch(path, {method, credentials: 'same-origin', cache:'no-store', headers:body ? {'Content-Type':'application/json'} : {}, body:body ? JSON.stringify(body) : undefined});
    if (!response.headers.get('content-type')?.includes('application/json')) throw Error('The local app is unavailable. Start Studio and open its localhost address.');
    const data = await response.json();
    if (!response.ok) {
      const error = Error(typeof data.detail === 'string' ? data.detail : data.error || 'The request could not be completed.');
      error.status = response.status; throw error;
    }
    return data;
  }
  function showDialog(kicker, title, content) {
    $('dialog-kicker').textContent = kicker; $('dialog-title').textContent = title; $('dialog-body').replaceChildren(content);
    $('close-dialog').hidden = requiredLogin;
    if (!$('modal').open) $('modal').showModal();
  }
  function close() { if (!requiredLogin) $('modal').close(); }
  $('close-dialog').onclick = close;
  $('modal').addEventListener('cancel', (e) => { if (requiredLogin) e.preventDefault(); });
  $('modal').addEventListener('click', e => { if (e.target === $('modal') && !requiredLogin) { const r = $('modal').getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) close(); } });
  function setView(view) {
    $('chat-pane').hidden = view !== 'chat'; $('files-pane').hidden = view !== 'files';
    document.querySelectorAll('.tab[data-view]').forEach(btn => { btn.classList.toggle('active',btn.dataset.view===view); btn.setAttribute('aria-current',btn.dataset.view===view?'page':'false'); });
    document.querySelectorAll('.rail-item[data-view]').forEach(btn => btn.classList.toggle('on',btn.dataset.view===view));
    if (view === 'files') renderFiles();
    $('sidebar').classList.remove('open');
  }
  document.querySelectorAll('[data-view]').forEach(btn => { btn.onclick = () => setView(btn.dataset.view); });
  $('mobile-menu').onclick = () => $('sidebar').classList.toggle('open');
  function editionText() {
    return browserEdition ? 'Browser demo · Public source sample' : 'Local workspace · ' + (settings.model === 'openai' ? 'OpenAI selected' : settings.model === 'ollama' ? 'Ollama selected' : 'Offline retrieval');
  }
  function summary() {
    $('setting-summary').textContent = settings.count + ' slides · ' + String(settings.language).toUpperCase() + ' · ' + settings.mode[0].toUpperCase() + settings.mode.slice(1);
    $('edition-note').textContent = editionText();
  }
  for (const [name, color, title, subtitle, prompt] of suggestions) {
    const b = el('button', null, 'prompt-card');
    b.title = prompt;
    const mark = el('span',null,'card-icon '+color); mark.append(icon(name));
    b.append(mark,el('strong',title),el('small',subtitle));
    b.onclick = () => { $('message').value = prompt; $('message').focus(); };
    $('prompts').append(b);
  }
  function detailText(parent, name, value) {
    if (!value) return;
    const p = el('p'); p.append(el('strong',name + ' '),document.createTextNode(formatted(value)));
    parent.append(p);
  }
  function inspect(slides, tab = 'preview') {
    let index = 0;
    function render() {
      const body = el('div');
      const tabs = el('div',null,'detail-nav');
      for (const [key,label] of [['preview','Slide preview'],['sources','Source evidence'],['check','Draft checks']]) {
        const b = button(label,() => { tab=key; render(); }, key===tab?'active':''); tabs.append(b);
      }
      body.append(tabs);
      if (tab === 'preview') {
        const s = slides[index], slide = el('div',null,'preview-slide');
        slide.append(el('small','SLIDE '+(index+1)+' / '+slides.length), el('h3',s.title), el('p',formatted(s.body || s.evidence)));
        const pager = el('div',null,'prev-next');
        const prev = button('Previous', () => { index--; render(); }); prev.disabled = index === 0;
        const next = button('Next', () => { index++; render(); }); next.disabled = index === slides.length-1;
        pager.append(prev,el('small','Content preview'),next);
        body.append(slide,pager); detailText(body,'Speaker notes',s.notes);
        detailText(body,'Source', [s.source,s.page ? 'Original slide '+s.page : ''].filter(Boolean));
      } else if (tab === 'sources') {
        slides.forEach((s,i) => {
          const d = el('details',null,'list-detail'); d.open = i === 0;
          d.append(el('summary',(i+1)+'. '+s.title));
          detailText(d,'Source',s.source); detailText(d,'Original slide',s.page); detailText(d,'Issued',s.issued); detailText(d,'Evidence',s.evidence); detailText(d,'Method',s.method);
          const href = safeLink(s.url);
          if (href) { const a = el('a','Open source ↗'); a.href=href; a.target='_blank'; a.rel='noopener noreferrer'; d.append(a); }
          body.append(d);
        });
      } else {
        body.append(el('p','These checks describe the outline currently on screen. Generating the PowerPoint also produces a downloadable QA report.'));
        for (const [label,test] of [['Slide title',s=>s.title],['Source attribution',s=>s.source],['Original slide number',s=>Number(s.page)>0],['Evidence excerpt',s=>formatted(s.evidence).trim()],['Speaker notes',s=>formatted(s.notes).trim()]]) {
          body.append(el('div',label+' · '+slides.filter(test).length+' / '+slides.length,'list-detail'));
        }
      }
      showDialog('PPT Builder','Review draft',body);
    }
    render();
  }
  function downloadLinks(version) {
    const links = el('div',null,'file-links');
    for (const [key,label] of [['pptx','PowerPoint'],['sources','Source report'],['qa','QA report']]) {
      const href = safeLink(version.files?.[key],true);
      if (!href) continue;
      const a=el('a',null,'inline-btn'+(key==='pptx'?' primary':''));
      a.href=href;
      if (browserEdition) a.download='PPT-Builder-'+version.id+'-'+key+(key==='pptx'?'.pptx':'.json');
      else a.setAttribute('download','');
      a.append(icon('download'),document.createTextNode(label));
      links.append(a);
    }
    return links;
  }
  function fileCard(v) {
    const row = el('div',null,'file-item'), box=el('div');
    box.append(el('h3','Presentation · '+v.id),el('small',[v.slide_count+' slides',v.template,v.language?.toUpperCase()].filter(Boolean).join(' · ')),downloadLinks(v));
    row.append(avatar(),box);
    return row;
  }
  function renderFiles() {
    const panel = $('files-pane'), versions = current.versions || [];
    panel.replaceChildren(el('h1','Shared files'),el('p','Downloads generated in this session.'));
    if (!versions.length) panel.append(el('div','Your PowerPoint, source report and QA report will appear here after you generate a deck.','empty-files'));
    else versions.slice().reverse().forEach(v => panel.append(fileCard(v)));
  }
  function renderRecents() {
    const rec = $('recents'); rec.replaceChildren();
    if (!current.topic) { rec.append(el('div','No drafts yet','recent-muted')); return; }
    const b=button(current.topic,() => {setView('chat'); $('scroll').scrollTop=$('scroll').scrollHeight;},'recent-item');
    b.title=current.topic; rec.append(b);
    if (current.versions?.length) rec.append(button('Generated files ('+current.versions.length+')',()=>setView('files'),'recent-item'));
  }
  function bubble(role, text, problem) {
    const row=el('article',null,'bubble-row '+(role==='user'?'user':'bot')+(problem?' problem':''));
    const body=el('div',null,'bubble-main');
    body.append(el('div',role==='user'?'You':'PPT Builder','bubble-meta'),el('div',text,'bubble'));
    if (role!=='user') row.append(avatar());
    row.append(body); return {row,body};
  }
  function showWorking(value) {
    busy=value;
    $('send').disabled=value;
    $('new-chat').disabled=value;
    document.querySelectorAll('[data-busy]').forEach(btn => {btn.disabled=value;});
    if (value) {
      const item=bubble('assistant','Working on your presentation…'); item.row.id='working';
      item.row.setAttribute('role','status'); $('thread').append(item.row); scrollBottom();
    } else $('working')?.remove();
  }
  function scrollBottom() { requestAnimationFrame(() => { $('scroll').scrollTop=$('scroll').scrollHeight; }); }
  function renderThread() {
    const thread=$('thread'); thread.replaceChildren(); $('welcome').hidden = !!(transcript.length || current.topic);
    let lastBody;
    for (const turn of transcript) {
      const item=bubble(turn.role,turn.text,turn.problem);
      thread.append(item.row);
      if (turn.role !== 'user' && !turn.problem) lastBody=item.body;
    }
    if ((current.slides?.length || current.versions?.length || current.warnings?.length) && !lastBody) {
      const item=bubble('assistant',current.reply || 'Your current draft'); thread.append(item.row); lastBody=item.body;
    }
    if (lastBody && current.slides?.length) {
      const card=el('div',null,'result-card'), actions=el('div',null,'result-actions'), slides=current.slides;
      card.append(el('h3','Presentation outline'),el('div',[slides.length+' slides',settings.mode,settings.audience].filter(Boolean).join(' · '),'stats-line'));
      const ol=el('ol',null,'slide-list'); slides.slice(0,3).forEach(s=>ol.append(el('li',s.title))); card.append(ol);
      if(slides.length>3) card.append(el('small','+'+(slides.length-3)+' more in preview','hint'));
      const make=button('Generate PowerPoint',()=>requestTurn(true),'inline-btn primary','slide'); make.dataset.busy='true'; make.disabled=busy;
      actions.append(make,button('Preview',()=>inspect(slides),'inline-btn'),button('Sources & checks',()=>inspect(slides,'sources'),'inline-btn'));
      card.append(actions); lastBody.append(card);
    }
    if (lastBody) {
      (current.warnings || []).forEach(w=>lastBody.append(el('p',formatted(w),'notes')));
      const latest=current.versions?.at(-1);
      if(latest) lastBody.append(fileCard(latest));
    }
    renderFiles(); renderRecents(); summary();
  }
  function transcriptKey() { return session.sessionId ? 'ppt-builder.teams.messages.'+session.sessionId : null; }
  function storeMessages() {
    const key=transcriptKey(); if(!key) return;
    try {sessionStorage.setItem(key,JSON.stringify(transcript.filter(x=>!x.problem).slice(-60)));} catch {}
  }
  function forgetMessages() {
    const key=transcriptKey();
    if(key) try {sessionStorage.removeItem(key);} catch {}
  }
  function applyState(next) {
    current=next || {};
    settings={...defaults,...settings,...current.settings};
    if (settings.model==='openai' && !session.modelAvailable) settings.model='offline';
    renderThread();
  }
  async function requestTurn(generate = false) {
    if (busy || requiredLogin) return;
    const field=$('message'), msg=field.value.trim();
    if (!generate && !msg) { field.focus(); return; }
    if (!generate && msg.length>1600) { info('Keep your message under 1,600 characters.'); return; }
    setView('chat');
    if (generate) transcript.push({role:'user',text:'Generate PowerPoint'});
    else {transcript.push({role:'user',text:msg}); field.value='';}
    renderThread(); showWorking(true);
    try {
      const next=await api('POST',generate?'/api/export':'/api/chat', generate ? {template:settings.template,settings} : {message:msg,settings});
      transcript.push({role:'assistant',text:next.reply || (generate?'Presentation generated.':'Draft updated.')});
      applyState(next); storeMessages();
    } catch (e) {
      transcript.push({role:'assistant',text:e.message,problem:true});
      if (!generate && !field.value) field.value=msg;
      renderThread();
      if (e.status === 401) { requiredLogin=true; loginDialog(); }
    } finally { showWorking(false); scrollBottom(); }
  }
  $('send').onclick=()=>requestTurn();
  $('message').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();requestTurn();}});
  function selectField(label, choices, value, grid, wide=false) {
    const wrap=el('label',label,wide?'wide':'');
    const select=el('select');
    choices.forEach(([key,text])=>{const option=el('option',text);option.value=key;select.append(option);});
    select.value=value;wrap.append(select);grid.append(wrap);return select;
  }
  function field(label,type,value,grid,wide=false) {
    const wrap=el('label',label,wide?'wide':''),input=el('input'); input.type=type;
    if(type!=='file') input.value=value==null?'':value;wrap.append(input);grid.append(wrap);return input;
  }
  function deckSettings() {
    if(requiredLogin||busy) return;
    const form=el('form'),grid=el('div',null,'form-grid');
    const count=field('Number of slides','number',settings.count,grid);count.min=1;count.max=20;count.required=true;
    const langOptions=[['en','English'],['zh','中文 · Chinese']];
    if (!browserEdition) langOptions.push(['fr','Français'],['es','Español'],['ar','العربية'],['ru','Русский']);
    if(!langOptions.some(([code])=>code===settings.language)) langOptions.push([settings.language,settings.language]);
    const lang=selectField('Output language',langOptions,settings.language,grid);
    const audience=field('Audience','text',settings.audience,grid);audience.maxLength=160;audience.placeholder='e.g. Veterinary officers';
    const year=field('Earliest source year','number',settings.min_year,grid);year.min=1900;year.max=2099;year.placeholder='Any year';
    const mode=selectField('Generation mode',[['hybrid','Hybrid'],['compilation','Compilation'],['reconstruction','Reconstruction']],settings.mode,grid);
    const templates=[['original','Standard'],['field','Field briefing · Warm']];
    if(!browserEdition) templates.push(['custom','Upload a template…']);
    const template=selectField('PowerPoint template',templates,settings.template,grid);
    let upload;
    if(!browserEdition) {
      upload=field('Template file (.pptx)','file','',grid,true);
      upload.accept='.pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation';
      upload.parentElement.hidden=template.value!=='custom';
      template.onchange=()=>{upload.parentElement.hidden=template.value!=='custom';};
    }
    const models=[['offline','Offline · Slide retrieval']];
    if(!browserEdition) models.push(['ollama','Ollama · Local model']);
    if(session.modelAvailable&&!browserEdition)models.push(['openai','OpenAI · Metered API']);
    const model=selectField('Model',models,settings.model,grid,true);
    const note=el('p','', 'form-note');
    const modeDescription=()=> {
      const descriptions=browserEdition
        ? {hybrid:'Alternates source briefs and rewritten evidence in the public sample.',compilation:'Uses source-brief layouts tied to the original slide numbers.', reconstruction:'Builds new editable slides from the public evidence summaries.'}
        : {hybrid:'Combines source slides and reconstructed content when the source files support it.',compilation:'Prioritizes original slide content and visuals.',reconstruction:'Rebuilds editable slides from the retrieved evidence.'};
      note.textContent=descriptions[mode.value]+' '+(model.value==='openai'?'Selected requests use the host’s API budget.':model.value==='ollama'?'Requires Ollama running on the host.':browserEdition?'English and Chinese are available.':'Offline output follows the languages available in the source material.');
    }; modeDescription();model.onchange=modeDescription;mode.onchange=modeDescription;
    const formError=el('p',null,'error-msg');formError.setAttribute('role','alert');
    const footer=el('div',null,'form-foot');
    const submit=el('button',current.slides?.length?'Apply to outline':'Save settings','regular-btn primary');submit.type='submit';
    footer.append(button('Cancel',close),submit);form.append(grid,note,formError,footer);
    form.onsubmit=async e=>{
      e.preventDefault(); submit.disabled=true;formError.textContent='';
      try {
        if(template.value==='custom'&&upload){
          const file=upload.files[0];
          if (!file && !custom && settings.template!=='custom') throw Error('Choose a .pptx file for the custom template.');
          if(file){
            const response=await fetch('/api/template',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'},body:file});
            if(!response.ok){const d=await response.json().catch(()=>({}));throw Error(d.detail||'Template upload failed.');}
            custom=true;
          }
        }
        const choice={count:Number(count.value),language:lang.value,audience:audience.value.trim(),min_year:year.value?Number(year.value):null,mode:mode.value,template:template.value,model:model.value};
        if(current.topic) {
          const updated=await api('POST','/api/chat',{message:'',settings:choice});
          transcript.push({role:'user',text:'Updated deck settings · '+choice.count+' slides · '+choice.language.toUpperCase()+' · '+choice.mode});
          transcript.push({role:'assistant',text:updated.reply || 'Outline settings updated.'});
          applyState(updated);storeMessages();scrollBottom();
        } else { settings=choice;summary(); }
        close();info('Deck settings updated.');
      } catch(err){formError.textContent=err.message;} finally{submit.disabled=false;}
    };
    showDialog('PPT Builder','Deck settings',form);
  }
  document.querySelectorAll('[data-open-settings]').forEach(b=>{b.onclick=deckSettings;});
  function help() {
    const panel=el('div');
    panel.append(el('p','Choose a sample prompt or enter your own briefing. Set the language, slide count and audience in Deck settings, then send your message.'));
    panel.append(el('p','Use Preview to read the outline and speaker notes. Sources & checks shows the source deck, original page and available evidence. Send a follow-up to refine the draft before generating.'));
    panel.append(el('p','Generate PowerPoint creates a version. Open Shared files to download the editable deck and its source and QA reports.'));
    panel.append(el('p',browserEdition?'This browser edition searches a curated public sample and keeps the current session in this tab. The local edition also supports host-configured models and the full prepared library.':'This session uses the corpus prepared on the host. Deck settings shows the available model options. Model-based output requires the corresponding service on the host.'));
    showDialog('Teams Mode','Using PPT Builder',panel);
  }
  $('help').onclick=help;
  function loginDialog() {
    const form=el('form'),grid=el('div',null,'form-grid'),error=el('p',null,'error-msg');
    error.setAttribute('role','alert');
    const role=selectField('Your role',[['user','Participant'],['developer','Developer']], 'user',grid,true);
    const pw=field('Access password','password','',grid,true);pw.required=true;pw.autocomplete='current-password';
    const footer=el('div',null,'form-foot'),submit=el('button','Sign in','regular-btn primary');submit.type='submit';
    form.append(el('p','Enter the access password provided by the person running this demo.'),grid,error,footer);footer.append(submit);
    form.onsubmit=async e=>{
      e.preventDefault();submit.disabled=true;
      try {
        const s=await api('POST','/api/login',{role:role.value,password:pw.value});
        const same=!!s.sessionId && s.sessionId===session.sessionId;
        if(!same){forgetMessages();transcript=[];settings={...defaults};custom=false;}
        session=s;requiredLogin=false;close();
        await loadHistory();showAccount();
      } catch(ex) {error.textContent=ex.message;} finally {submit.disabled=false;}
    };
    showDialog('Teams Mode','Sign in to this workspace',form);
  }
  function showAccount(){
    $('account').textContent=browserEdition?'G':session.role==='developer'?'D':'U';
    $('account').title=browserEdition?'Browser guest session':'Session: '+(session.role||'signed out');
  }
  $('account').onclick=()=>{
    if(requiredLogin){loginDialog();return;}
    const body=el('div');
    body.append(el('p',browserEdition?'You are using the public sample in this browser tab.':'Signed in as '+(session.role==='developer'?'a developer.':'a participant.')));
    if(!browserEdition){
      const controls=el('div',null,'form-foot');
      controls.append(button('Switch role',()=>{ loginDialog(); }),button('Sign out',async()=>{
        try{await api('POST','/api/logout',{});forgetMessages();transcript=[];current={};settings={...defaults};session={};custom=false;renderThread();requiredLogin=true;loginDialog();}
        catch(e){info(e.message);}
      }));body.append(controls);
    }
    showDialog('Teams Mode','Session details',body);
  };
  function startOver() {
    if(busy||requiredLogin)return;
    const panel=el('div');panel.append(el('p','Starting a new brief clears this session’s messages, drafts and generated files. Download any files you want to keep first.'));
    const footer=el('div',null,'form-foot');
    const reset=button('Start new brief',async()=>{
      reset.disabled=true;try{
        const result=await api('POST','/api/reset',{});forgetMessages();
        if(result.sessionId) session={...session,sessionId:result.sessionId};
        transcript=[];current={};settings={...defaults};custom=false;$('message').value='';close();setView('chat');renderThread();$('message').focus();
      }catch(e){info(e.message);}finally{reset.disabled=false;}
    },'regular-btn primary');
    footer.append(button('Cancel',close),reset);panel.append(footer);showDialog('Current session','Start a new brief?',panel);
  }
  $('new-chat').onclick=startOver;
  function searchWorkspace(){
    if(requiredLogin)return;
    const box=el('div'),input=el('input'),results=el('div',null,'search-items');
    input.type='search';input.placeholder='Search messages, slides and files';input.setAttribute('aria-label',input.placeholder);
    function update(){
      const q=input.value.trim().toLowerCase();results.replaceChildren();
      const options=[
        ['PPT Builder · Chat',()=>setView('chat')],
        ['Shared files',()=>setView('files')],
        ['Developer Mode',()=>{location.href='studio.html';}],
        ...transcript.map((m,i)=>[m.text,()=>{setView('chat');$('thread').children[i]?.scrollIntoView({block:'center'});}]),
        ...(current.slides||[]).map((s,i)=>['Slide '+(i+1)+' · '+s.title,()=>inspect([s])]),
        ...(current.versions||[]).map(v=>['PowerPoint · '+v.id,()=>setView('files')])
      ].filter(([label])=>String(label).toLowerCase().includes(q));
      for(const [label,action] of options.slice(0,30)){const b=button(String(label).slice(0,150),()=>{close();action();},'');results.append(b);}
      if(!options.length)results.append(el('p','No results in this workspace.'));
    }
    input.oninput=update;box.append(input,results);update();showDialog('Teams Mode','Search this workspace',box);input.focus();
  }
  $('open-search').onclick=searchWorkspace;
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();searchWorkspace();}});
  async function loadHistory() {
    const snapshot=await api('GET','/api/history');
    if(Array.isArray(snapshot.messages) && snapshot.messages.length) {
      transcript=snapshot.messages.filter(m=>m?.role==='user'||m?.role==='assistant').map(m=>({role:m.role,text:formatted(m.text||m.content||m.message)})).filter(m=>m.text);
    }
    if(!transcript.length && transcriptKey()) {
      try{const stored=JSON.parse(sessionStorage.getItem(transcriptKey()) || '[]');if(Array.isArray(stored))transcript=stored.filter(m=>['user','assistant'].includes(m.role)&&typeof m.text==='string');}catch{}
    }
    if(!transcript.length && snapshot.topic){transcript.push({role:'user',text:snapshot.topic});if(snapshot.reply)transcript.push({role:'assistant',text:snapshot.reply});}
    applyState(snapshot);if(transcript.length)scrollBottom();
  }
  async function init(){
    renderThread();
    try{
      session=await api('GET','/api/status');requiredLogin=!!session.requiresLogin && !session.authenticated;
      showAccount();if(requiredLogin){loginDialog();return;}
      await loadHistory();
    }catch(e){
      const body=el('div');body.append(el('p',e.message),button('Retry',()=>{close();init();},'regular-btn primary'));
      showDialog('Teams Mode','Workspace unavailable',body);
    }
  }
  init();
})();
