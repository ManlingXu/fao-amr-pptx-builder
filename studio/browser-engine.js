/* Standalone public edition. Only curated public-source summaries enter this tab. */
(() => {
  'use strict';
  if (!window.BROWSER_EDITION) return;
  const storageKey = 'ppt-builder.browser.tab.v1';
  const defaults = {count: 5, language: 'en', template: 'original', audience: '', mode: 'hybrid', model: 'offline', min_year: null};
  const fresh = () => ({topic: '', settings: {...defaults}, slides: [], versions: [], messages: [], reply: '', warnings: []});
  let state = fresh();
  try { state = JSON.parse(sessionStorage.getItem(storageKey) || 'null') || state; } catch {}
  const files = new Map();
  let catalogPromise;
  let libraryPromise;
  const save = () => { try {sessionStorage.setItem(storageKey, JSON.stringify(state));} catch {} };
  const corpus = () => {
    if (!catalogPromise) catalogPromise = fetch(new URL('evidence.json', document.baseURI)).then(r => {
      if (!r.ok) throw Error('The public source collection could not be loaded. Refresh to retry.');
      return r.json();
    }).catch(e => {catalogPromise = null; throw e;});
    return catalogPromise;
  };
  function loadPowerPoint() {
    if (!libraryPromise) libraryPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = new URL('vendor/pptxgen.bundle.js', document.baseURI).href;
      script.onload = () => resolve(window.PptxGenJS);
      script.onerror = () => {libraryPromise = null; reject(Error('The PowerPoint exporter could not be loaded. Please retry.'));};
      document.head.append(script);
    });
    return libraryPromise;
  }
  const groups = {
    uk: /\buk\b|united kingdom|british|英国/i, italy: /italy|italian|意大利/i, zambia: /zambi|赞比亚/i, vietnam: /viet\s?nam|越南/i, poultry: /poultry|chicken|flock|家禽|养鸡|鸡群/i,
    farming: /farm|producer|livestock|畜牧|农户|养殖/i, stewardship: /steward|prudent|responsible use|管理|审慎/i,
    surveillance: /surveill|monitor|监测/i, outreach: /outreach|communicat|awareness|宣传|沟通/i,
    onehealth: /one health|同一健康|一个健康/i, animal: /animal|veterin|兽医|动物/i,
    policy: /polic|legislat|regulat|政策|法规/i, amr: /\bamr\b|resistan|抗微生物|耐药/i,
    training: /train|learn|培训|学习/i, prevention: /prevent|biosecur|预防|生物安全/i,
  };
  const terms = str => String(str).toLowerCase().match(/[a-z0-9]{3,}/g) || [];
  const stops = new Set('create make please slide slides deck briefing presentation give build about prepare make audience editable speakers for the with and into how what source draft slide make country evidence five three ten two english chinese version using training deck'.split(' '));
  const concepts = str => Object.entries(groups).filter(([,rx])=>rx.test(str)).map(([id])=>id);
  function ranked(query, cfg, rows) {
    const keywords = [...new Set(terms(query).filter(w=>!stops.has(w)))], family = concepts(query);
    const places = family.filter(k=>['zambia','vietnam','uk','italy'].includes(k));
    const unknownPlace = /\b(?:brazil|australia|canada|japan|kenya|argentina)\b|巴西|澳大利亚|加拿大|日本|肯尼亚|阿根廷/i.test(query);
    if(unknownPlace && !rows.some(r=>String(query).toLowerCase().includes(String(r.country).toLowerCase()))) return [];
    const pool = [];
    for (const row of rows) {
      if (cfg.min_year && !(Number(String(row.issued).slice(0,4)) >= cfg.min_year)) continue;
      const tags = (row.tags || []).join(' ');
      const fields = [row.title,row.title_zh,row.evidence,row.evidence_zh,row.source,tags].join(' ');
      if (places.some(p=> !groups[p].test(row.country || row.source))) continue;
      const normalized = fields.toLowerCase(), topical = [row.title,row.evidence,tags].join(' ').toLowerCase();
      const common = family.filter(k=>groups[k].test(fields)).length;
      const exact = keywords.reduce((sum,w)=> sum + (topical.includes(w) ? 4 : normalized.includes(w) ? 1 : 0), 0);
      if (common || exact) pool.push({row, score: common * 2 + exact});
    }
    return pool.sort((a,b)=>b.score-a.score).slice(0,cfg.count).map(x=>x.row);
  }
  function configuration(base, patch, message) {
    const cfg={...base,...patch,model:'offline'};
    const count=message.match(/(?:\b(\d{1,2})\s*[- ]?slides?\b|(\d{1,2})\s*[张页])/i);
    if(count) cfg.count=Number(count[1]||count[2]);
    cfg.count=Math.max(1,Math.min(20,parseInt(cfg.count,10)||defaults.count));
    if(/(?:in chinese|中文|mandarin)/i.test(message)) cfg.language='zh';
    if(/(?:in english|英文|英语)/i.test(message)) cfg.language='en';
    if(/^(zh|中文|chinese)/i.test(cfg.language)) cfg.language='zh';
    const year=message.match(/(?:since|from|after|自|从)\s*(20\d{2})/i);
    if(year) cfg.min_year=Number(year[1])+(/after\s*20/i.test(message)?1:0);
    cfg.min_year=parseInt(cfg.min_year,10)||null;
    if(!['compilation','hybrid','reconstruction'].includes(cfg.mode)) cfg.mode='hybrid';
    return cfg;
  }
  const isZh = cfg => cfg.language==='zh';
  const scope = (rows) => ({decks:new Set(rows.map(x=>x.source)).size, slides:rows.length});
  function slidesFor(query,cfg,rows) {
    const zh=isZh(cfg);
    return ranked(query,cfg,rows).map((row,i)=>{
      const evidence=zh?(row.evidence_zh||row.evidence):row.evidence;
      const method=cfg.mode==='compilation'||(cfg.mode==='hybrid'&&i%2===1)?'Source brief':'Reconstruction';
      const audience=String(cfg.audience||'').trim();
      const title=zh?(row.title_zh||row.title):row.title;
      const cue=zh?'引导听众将这项原则联系到自己的工作，并请他们举一个可以采取行动的例子。':'Ask the audience where this principle applies in their work and invite one practical example.';
      const notes=[title,evidence,audience?(zh?'面向 ':'For ')+audience+' — '+cue:cue, row.source+' · '+row.page+' · '+row.url].join('\n\n');
      return {title,evidence,source:row.source,page:row.page,url:row.url,issued:row.issued,notes,method,id:row.id};
    });
  }
  function qa(version) {
    const slides=version.slides;
    const checks=[
      {name:'Requested slide count',pass:slides.length===version.settings.count,detail:slides.length+' / '+version.settings.count},
      {name:'Traceable external source and original slide',pass:slides.every(s=>/^https?:\/\//.test(s.url)&&Number(s.page)>0)},
      {name:'Unique evidence',pass:new Set(slides.map(s=>s.id)).size===slides.length},
      {name:'Speaker notes on every slide',pass:slides.every(s=>Boolean(s.notes))},
      {name:'Minimum source year',pass:slides.every(s=>!version.settings.min_year||Number(String(s.issued).slice(0,4))>=version.settings.min_year)},
    ];
    return {version:version.id,edition:'Browser public-source collection',scope:'Structural checks; human review of relevance, translation and suitability remains necessary.',checks,passed:checks.every(c=>c.pass)};
  }
  async function buildFiles(v) {
    if (files.has(v.id)) return files.get(v.id);
    const Engine=await loadPowerPoint();
    const p=new Engine(); p.layout='LAYOUT_WIDE'; p.author='PPT Builder'; p.subject='Public evidence briefing'; p.title=v.topic;
    const warm=v.settings.template==='field'; const accent=warm?'8B4D30':'305F59', background=warm?'FBF5EB':'F2F7F4', ink=warm?'382C29':'1D3531';
    const lang=isZh(v.settings)?'zh-CN':'en-US';const face=isZh(v.settings)?'Microsoft YaHei':'Aptos';
    const label=(s,txt,x,y,w,h,extra={})=>s.addText(String(txt||''),{x,y,w,h,margin:0,fontFace:face,fontSize:14,color:ink,breakLine:false,align:'left',valign:'mid',fit:'shrink',lang,...extra});
    v.slides.forEach((entry,index)=>{
      const s=p.addSlide();
      const sourceBrief=entry.method==='Source brief';
      s.background={color:sourceBrief?'FFFFFF':background};
      s.addShape(p.ShapeType.rect,{x:0,y:0,w:13.333,h:0.10,line:{transparency:100},fill:{color:accent}});
      label(s,'PPT BUILDER   /   '+(isZh(v.settings)?'公开资料简报':'PUBLIC SOURCE BRIEFING'),0.77,0.52,10,.3,{fontSize:12,bold:true,color:accent,charSpacing:2});
      label(s,String(index+1).padStart(2,'0')+'  /  '+String(v.slides.length).padStart(2,'0'),11.0,.51,1.55,.30,{fontSize:12,align:'right',color:accent});
      label(s,entry.title,.77,1.12,11.85,1.35,{fontSize:35,bold:true});
      if(sourceBrief) s.addShape(p.ShapeType.rect,{x:.78,y:2.88,w:.065,h:1.65,line:{transparency:100},fill:{color:accent}});
      label(s,entry.evidence,sourceBrief?1.05:.80,2.70,11.1,2.30,{fontSize:24,valign:'top'});
      s.addShape(p.ShapeType.line,{x:.78,y:5.75,w:11.75,h:0,line:{color:'C6D2CE',width:1}});
      label(s,entry.source,.80,5.98,11.75,.48,{fontSize:15,bold:true});
      label(s,(isZh(v.settings)?'原始页码 ':'Original slide ')+entry.page+'     ·     '+String(entry.issued|| (isZh(v.settings)?'日期未知':'Date unavailable')),.80,6.52,8,.38,{fontSize:13,color:accent});
      label(s,isZh(v.settings)?'查看来源 ↗':'Open source ↗',9.1,6.52,3.4,.38,{fontSize:14,align:'right',hyperlink:{url:entry.url},color:accent});
      s.addNotes(entry.notes);
    });
    const blob=await p.write({outputType:'blob'});
    const jsonLink=obj=>URL.createObjectURL(new Blob([JSON.stringify(obj,null,2)],{type:'application/json'}));
    const links={pptx:URL.createObjectURL(blob),sources:jsonLink({version:v.id,topic:v.topic,slides:v.slides.map((s,i)=>({output_slide:i+1,source:s.source,original_slide:s.page,url:s.url,issued:s.issued,evidence:s.evidence,method:s.method}))}),qa:jsonLink(qa(v))};
    files.set(v.id,links);return links;
  }
  async function snapshot(rows) {
    const versions=[];
    for(const v of state.versions) versions.push({id:v.id,slide_count:v.slides.length,template:v.settings.template,mode:v.settings.mode,language:v.settings.language,created_at:v.created_at,files:await buildFiles(v)});
    return {...state,versions,stats:scope(rows),model_used:'offline',edition:'browser'};
  }
  const addMessage=(role,content)=>{state.messages.push({role,content,text:content}); if(state.messages.length>60)state.messages.splice(0,2);};
  window.browserAPI=async function browserAPI(method,path,body={}) {
    const route=new URL(path,location.href).pathname;
    const rows=await corpus();
    if(route==='/api/session'||route==='/api/status')return {edition:'browser',authenticated:true,role:'developer',requiresLogin:false,sessionId:'browser-tab',modelAvailable:false,stats:scope(rows)};
    if(route==='/api/developer')return {edition:'browser',role:'developer',runtime:{mode:'Browser demo',provider:'In-browser',model:'Offline retrieval',...scope(rows),corpus:'Public source summaries',sessions:1},limits:{model_calls:0,token_budget:0},usage:{model_calls:0,tokens_reserved:0}, events:state.versions.map(v=>({time:v.created_at,action:'Export '+v.id,outcome:'Completed'})),deployment:{tunnel_enabled:false}};
    if(route==='/api/reset'||route==='/api/logout'){
      for(const links of files.values()) Object.values(links).forEach(href=>URL.revokeObjectURL(href));
      files.clear(); state=fresh();save();return snapshot(rows);
    }
    if(route==='/api/history')return snapshot(rows);
    if(route==='/api/chat'&&body.action!=='generate'){
      const msg=String(body.message||'').trim();
      const settings=configuration(state.settings,body.settings||{},msg);
      if(!['zh','en'].includes(settings.language))throw Error('The browser collection supports English and Chinese. Choose one of these languages.');
      if(!msg&&!state.topic)throw Error('Enter a briefing topic first.');
      const why=msg.match(/^(?:why (?:did you )?(?:select |choose )?|explain |source (?:for )?)(?:slide )?(\d+)[?.! ]*$/i)||msg.match(/^(?:为什么选|解释|来源).*?第?\s*(\d+)\s*页[？?]?$/);
      const move=msg.match(/^move (?:slide )?(\d+) to (?:slide )?(\d+)[.! ]*$/i)||msg.match(/^(?:把|将)?第?(\d+)页移(?:到|至)第?(\d+)页$/);
      const remove=msg.match(/^(?:remove|delete) (?:slide )?(\d+)[.! ]*$/i)||msg.match(/^(?:删除|移除)第?(\d+)页$/);
      const replace=msg.match(/^replace (?:slide )?(\d+) with (.+)$/i)||msg.match(/^(?:把|将)?第?(\d+)页(?:替换|换|改)(?:为|成)(.+)$/);
      if(state.topic&&(why||move||remove||replace)){
        const idx=Number((why||move||remove||replace)[1])-1,dst=move?Number(move[2])-1:idx;
        if(Math.min(idx,dst)<0||Math.max(idx,dst)>=state.slides.length)throw Error('Choose a slide number in the current outline.');
        const s=state.slides[idx];
        if(why)state.reply=s.source+' · '+s.page+'\n'+s.evidence;
        if(move){state.slides.splice(dst,0,state.slides.splice(idx,1)[0]);state.reply='Moved slide '+(idx+1)+' to '+(dst+1)+'.';}
        if(remove){state.slides.splice(idx,1);state.settings.count=Math.max(1,state.slides.length);state.reply='Removed slide '+(idx+1)+'.';}
        if(replace){
          const used=new Set(state.slides.map(s=>s.id)), place=concepts(state.topic).filter(k=>['zambia','vietnam','uk','italy'].includes(k));
          const options=slidesFor(place.join(' ')+' '+replace[2],{...settings,count:1},rows.filter(x=>!used.has(x.id)));
          if(options.length){state.slides[idx]=options[0];state.reply='Replaced slide '+(idx+1)+'.';}
          else state.reply='No unused source page matched that replacement.';
        }
        addMessage('user',msg);addMessage('assistant',state.reply);save();return snapshot(rows);
      }
      if(state.topic&&/^(?:generate(?: (?:the |my )?(?:powerpoint|deck|pptx))?|confirm|生成(?:幻灯片|演示文稿|PPT)?|确认生成)[.!。 ]*$/i.test(msg))return window.browserAPI('POST','/api/export',{settings});
      const revise=state.topic && (!msg || /^apply settings$/i.test(msg) || /^(?:change|make (?:it|this)|switch|revise|instead|use (?:the|a|an|\d)|shorten|expand|focus|translate|add|remove|调整|改|换|缩|扩|聚焦|用|请改|请用)/i.test(msg));
      const substantive=concepts(msg).filter(k=>!['amr','training'].includes(k)).length>0;
      const query=revise?(substantive?state.topic+' · '+msg:state.topic):(msg||state.topic);
      state.topic=query;state.settings=settings;
      state.slides=slidesFor(query,settings,rows);state.warnings=[];
      const zh=isZh(settings),n=state.slides.length;
      if(n<settings.count)state.warnings.push(zh?'当前资料只支持 '+n+' 页。':'The available evidence supports '+n+' of '+settings.count+' requested slides.');
      state.reply= n?(zh?'已为你拟好 '+n+' 页大纲。可以查看原始出处，或继续调整后生成 PowerPoint。':'I found evidence for '+n+' slides. Review the outline and its sources, or refine the brief before generating your PowerPoint.'):(zh?'当前公开样本中没有符合主题和年份的资料。可以尝试兽医审慎用药、家禽养殖或调整年份。':'I found no matching slides in this public sample. Try veterinary stewardship or poultry, or adjust the source year.');
      if(msg)addMessage('user',msg);addMessage('assistant',state.reply);save();return snapshot(rows);
    }
    if(route==='/api/export'||(route==='/api/chat'&&body.action==='generate')){
      const prior=body.version?state.versions.find(v=>v.id===body.version):null;
      if(body.version&&!prior)throw Error('That version is unavailable in this tab.');
      if(!(prior?.slides||state.slides).length)throw Error('Choose a topic with matching sources before generating a PowerPoint.');
      const cfg={...(prior?.settings||state.settings),...(body.settings||{})};
      if(body.template)cfg.template=body.template;
      const v={id:'v'+((state.sequence||0)+1),topic:prior?.topic||state.topic,settings:cfg,created_at:new Date().toISOString(),slides:structuredClone(prior?.slides||state.slides)};
      await buildFiles(v);
      state.sequence=(state.sequence||0)+1; state.versions.push(v);
      if(state.versions.length>12){const old=state.versions.shift();Object.values(files.get(old.id)||{}).forEach(url=>URL.revokeObjectURL(url));files.delete(old.id);}
      state.reply=isZh(cfg)?'可编辑的 PowerPoint、逐页来源和质量报告已生成。':'Your editable PowerPoint, slide-by-slide source report and QA report are ready.';
      addMessage('assistant',state.reply);save();return snapshot(rows);
    }
    throw Error('This operation requires the local edition.');
  };
})();
