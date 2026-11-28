"use strict";

const PROJECT = "https://github.com/ManlingXu/fao-amr-pptx-builder/blob/main/";
const BLUEPRINT = "integrations/copilot-studio/";
const GUIDE = "https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/overview";
const sections = [
  ["overview", "Overview", "grid", "Workspace"],
  ["identity", "Identity", "id", "Agent configuration"],
  ["model", "Model", "spark", "Agent configuration"],
  ["instructions", "Instructions", "text", "Agent configuration"],
  ["knowledge", "Knowledge", "book", "Agent configuration"],
  ["skills", "Skills", "puzzle", "Agent configuration"],
  ["tools", "Tools", "tools", "Agent configuration"],
  ["workflows", "Workflows", "flow", "Orchestration"],
  ["hooks", "Hooks", "bolt", "Orchestration"],
  ["memory", "Memory", "stack", "Orchestration"],
  ["evaluation", "Evaluation", "check", "Operations"],
  ["monitor", "Monitor", "activity", "Operations"],
  ["channels", "Channels", "chat", "Operations"],
  ["deployment", "Deployment", "send", "Operations"],
];
const paths = {
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  id:'<rect x="2.5" y="5" width="19" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M5.7 15.4q3.3-4.6 6.6 0m2.4-5.3h3.5m-3.5 3.6h3.5"/>',
  spark:'<path d="m12 3 1.9 6.8L20 12l-6.1 2.1L12 21l-2-6.9L4 12l6-2.2L12 3Zm6.5.5v3m-1.5-1.5h3"/>',
  text:'<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 11h7M9 14h7M9 17h5"/>',
  book:'<path d="M12 5.9Q6.4 2.7 2.5 5v14q4.5-2.2 9.5 1 4.8-3.2 9.5-1V5q-4.4-2.2-9.5.9V20"/>',
  puzzle:'<path d="M4 5h5a3 3 0 1 1 5.7 0h4.8v5a3 3 0 1 0 0 5.7V20h-5a3 3 0 1 0-5.7 0H4z"/>',
  tools:'<path d="m8 15 7-7m0-1a4 4 0 0 1 5-4l-2.4 2.5.6 2 2.2.6L22 6a4.5 4.5 0 0 1-6.5 5L8 19a2.5 2.5 0 0 1-3.5-3.5l3-3"/>',
  flow:'<rect x="8" y="2" width="8" height="5" rx="1"/><rect x="2" y="17" width="7" height="5" rx="1"/><rect x="15" y="17" width="7" height="5" rx="1"/><path d="M12 7v5M5.5 17v-5h13v5"/>',
  bolt:'<path d="m13.5 2-9 12H11l-.5 8L20 9h-7z"/>',
  stack:'<path d="m12 3 9.5 5L12 13 2.5 8 12 3Zm-9 9 9 5 9-5m-18 4 9 5 9-5"/>',
  check:'<rect x="4" y="4" width="16" height="17" rx="2"/><path d="M9 4V2h6v2m-7 9 3 3 5-7"/>',
  activity:'<path d="M2 13h5l3-9 4 16 3-8h5"/>',chat:'<path d="M20 15a3 3 0 0 1-3 3H9l-5 3v-4a3 3 0 0 1-1-2V6a3 3 0 0 1 3-3h11a3 3 0 0 1 3 3v9Z"/><path d="M7 8h9m-9 4h5"/>',
  send:'<path d="m3 10 18-7-7 18-3-8-8-3Zm8 3L21 3"/>',
  external:'<path d="M13 4h7v7m0-7-10 10M9 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15 15 5 5"/>',chev:'<path d="m9 5 7 7-7 7"/>',
  arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>',lock:'<rect x="4.5" y="10" width="15" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-11v1"/>',menu:'<path d="M3 6h18M3 12h18M3 18h18"/>',refresh:'<path d="M20 7a8 8 0 1 0 .2 9M20 2v5h-5"/>',
};
const app = document.getElementById("app");
const browserEdition = window.BROWSER_EDITION === true;
let config, current, dev = {}, session = {}, filter = "";

function e(value) {
  return String(value ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function icon(key){return '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">'+(paths[key]||paths.grid)+'</svg>'}
function val(v){return v == null ? "—" : typeof v === "number" ? v.toLocaleString("en-US") : String(v)}
function row(k,v){return '<div class="config-row"><span>'+e(k)+'</span><strong>'+e(val(v))+'</strong></div>'}
function card(title,body,desc=""){return '<section class="panel"><h2>'+e(title)+'</h2>'+(desc?'<p class="subtitle">'+e(desc)+'</p>':'')+body+'</section>'}
function source(text,path){return '<a class="src" href="'+e(path.startsWith("https://")?path:PROJECT+path)+'" target="_blank" rel="noopener noreferrer">'+e(text)+' '+icon("external")+'</a>'}
function note(s){return '<div class="info-note">'+icon("info")+'<span>'+e(s)+'</span></div>'}
function sectionLink(id,label){return '<a class="panel-link" href="#'+id+'">'+e(label)+' '+icon("arrow")+'</a>'}
function fold(label,content,tag=""){return '<details class="accordion"><summary>'+e(label)+(tag?' <span class="tag">'+e(tag)+'</span>':'')+'</summary><div class="accordion-body">'+content+'</div></details>'}
function paragraph(s){return '<p>'+e(s)+'</p>'}
function numbered(items){return '<ol>'+items.map(s=>'<li>'+e(s)+'</li>').join("")+'</ol>'}
function code(s){return '<pre>'+e(s)+'</pre>'}
function configList(items){return '<div class="config-list">'+items.map(([k,v])=>row(k,v)).join("")+'</div>'}
function twoCards(left,right){return '<div class="columns">'+left+right+'</div>'}
function headerInfo(k){return sections.find(i=>i[0]===k)||sections[0]}
function workspaceName(){return browserEdition?"Browser edition":dev.runtime?.mode==="tunnel"?"Shared local runtime":"Local runtime"}
function runtimeRows(){
  const r=dev.runtime||{};
  return configList([["Environment",workspaceName()],["Model access",session.modelAvailable?"OpenAI available on request":"Offline"],["Searchable library",r.decks==null?"—":val(r.decks)+" decks"],["Source pages",r.slides==null?"—":val(r.slides)]]);
}
function feature(id,description,colour=""){
  const [,label,key]=headerInfo(id);
  return '<a class="feature" href="#'+id+'"><div class="feature-top"><span class="icon-tile '+colour+'">'+icon(key)+'</span><span class="chev">'+icon("chev")+'</span></div><h3>'+label+'</h3><p>'+e(description)+'</p></a>';
}
function activeSteps(){return ["Collect the presentation brief","Find and review source pages","Confirm the outline","Export the deck and reports"]}
function overview(){
  return '<div class="hero"><div class="hero-copy"><div class="eyebrow">Agent workspace</div><h1>PPT Builder</h1><p>Turn presentation requests into editable PowerPoint drafts with evidence from the AMR slide library.</p><div class="hero-actions"><a class="button primary" href="index.html">'+icon("chat")+' Preview agent</a><a class="button" href="#workflows">View workflow '+icon("arrow")+'</a></div></div><div class="diagram" aria-hidden="true"><div class="paper back"></div><div class="paper middle"></div><div class="paper face"><div class="thumb"><i></i><i></i><i></i></div><div class="plot"><i></i><i></i><i></i></div></div></div></div>'+
    '<div class="section-heading"><h2>Agent configuration</h2></div><div class="feature-grid">'+
    feature("instructions","Read the rules for selecting and citing slides.")+feature("knowledge","Inspect source coverage and date evidence.","blue")+feature("tools",config.tools.length+" operations in the connector definition.","orange")+'</div>'+
    '<div class="overview-lower">'+card("Presentation workflow",'<div class="pipeline">'+activeSteps().map(s=>'<div class="pipe-step"><i class="pip"></i>'+e(s)+'</div>').join("")+'</div>'+sectionLink("workflows","Inspect workflow"))+
    card("Runtime",runtimeRows()+sectionLink("monitor","Open monitor"))+'</div>';
}
const descriptions = {
  identity:"The agent name, audience and access model for this edition.",
  model:"Inspect the active runtime and the options for model-assisted drafting.",
  instructions:"Read the implementation rules and the full instructions prepared for a Copilot Studio agent.",
  knowledge:"Compare the project catalogue with the sources available to this runtime.",
  skills:"Inspect the four skills and the prompt definitions prepared for the organizational agent.",
  tools:"Inspect the web app actions and the tool definitions prepared for the organizational connector.",
  workflows:"Follow a request from the brief to an editable presentation and its source report.",
  hooks:"See where the application checks inputs, limits and output ownership.",
  memory:"See which state supports follow-up requests and revisions.",
  evaluation:"Inspect the checks used to evaluate sources, output files and runtime behavior.",
  monitor:"Review this runtime’s available counters and recorded events.",
  channels:"See how people can open the agent in each environment.",
  deployment:"Review the running edition and the dependencies for an organizational release."
};
function dataSection(id){
  const r=dev.runtime||{}, l=dev.limits||{}, u=dev.usage||{}, hosted=browserEdition;
  switch(id){
    case "identity": return card("Agent details",configList([["Name","PPT Builder"],["Purpose","Find relevant source slides and create editable presentation drafts."],["Domain","Antimicrobial resistance and One Health"],["Audience","Presentation authors, reviewers and project developers"],["Environment",workspaceName()],["Access",hosted?"Public demo configuration":"Authenticated developer"]]))+
      card("Authoring surface",'<p class="subtitle">Build, Preview, Evaluate and Monitor follow the Copilot Studio authoring model. This workspace presents the configuration and runtime of the PPT Builder prototype.</p>'+source("Microsoft authoring reference",GUIDE));
    case "model": return card("Model configuration",configList([["Default","Offline retrieval and drafting"],["OpenAI access",hosted?"Unavailable in the browser edition":session.modelAvailable?"Enabled by host · optional per request":"Disabled on this host"],["Configured OpenAI model",r.model||"—"],["Local model",hosted?"Unavailable in this edition":"Optional Ollama installation on the host (default qwen3:4b)"],["Session model use","Select the model in Teams mode"],["Model call ceiling",l.model_calls],["Reserved token ceiling",l.token_budget]]))+
      note(hosted?"The browser runs offline drafting against its bundled source collection. An authenticated local host is required for optional OpenAI calls.":"Optional model use requires a host configuration and an explicit model selection. Review the provider and request limits in Monitor.")+
      source("Local model adapter","presentation_search/studio_model.py");
    case "instructions": return card("Local drafting rules",'<div class="reader">'+paragraph("Select source pages from the active corpus. Keep the source deck, original page and evidence with each selection. Retain the current brief while the author refines the draft. Confirm the selection before writing deliverables.")+
      fold("Model instruction · slide drafting",code(config.modelInstructions.ADAPT_INSTRUCTIONS))+fold("Model instruction · dialogue and revisions",code(config.modelInstructions.DIALOGUE_INSTRUCTIONS))+'</div>'+source("Local implementation","presentation_search/studio_service.py"))+
      card("Copilot Studio agent instructions",'<details class="accordion"><summary>Read the full instructions</summary><div class="reader">'+config.instructions.split(/\n+/).filter(Boolean).map(paragraph).join("")+'</div></details>'+source("Open instruction file",BLUEPRINT+"agent-instructions-en.txt"),"Full text from the repository, prepared for the organizational agent.");
    case "knowledge": return twoCards(card("Available in this runtime",configList([["Source decks",r.decks],["Source pages",r.slides],["Corpus",r.corpus||"See the active host configuration"]]),hosted?"The browser searches its bundled source collection.":"Counts reflect the corpus loaded on this host."),card("Full project catalogue",configList([["Catalogued decks",config.catalog.decks],["Listed source pages",config.catalog.pages]])+source("Browse the source catalogue","examples/public_corpus/amr/catalog.csv"),"Publisher files are acquired and verified separately on the local host."))+
      card("Evidence used during review",configList([["Provenance","Original source deck, page number and source URL where supplied"],["Date evidence","Known publication dates and source versions, with unknown dates retained as unknown"],["Selection","Topic terms, evidence overlap and source diversity"]])+source("Index and selection logic","presentation_search/brief_index.py"));
    case "skills": return card("Agent skills",config.migrationSkills.map(s=>fold(s.name,paragraph(s.description)+s.body.split(/\n\n+/).map(paragraph).join("")+source("Open skill file",BLUEPRINT+s.file))).join(""),"Four project skill definitions for the maker handoff.")+
      note("The prompt blueprints below define the inputs and instructions for a manually configured Copilot Studio workflow.")+
      card("Prompt definitions",config.skills.map((s,i)=>fold(["Presentation brief","Query expansion","Candidate reranking","Layout decision"][i],paragraph(s.purpose)+'<h3>Inputs</h3>'+code(s.inputs.join(", "))+'<h3>Instructions</h3>'+numbered(s.instructions)+source("Open prompt blueprint",BLUEPRINT+s.file))).join(""));
    case "tools": return card("Web app actions",configList([["POST /api/chat","Create or revise an evidence-based outline"],["POST /api/export","Generate the confirmed presentation and reports"],["GET /api/history","Inspect the current session"],["GET /api/developer","Read developer runtime counters"]]),hosted?"Browser edition implements the demo actions within this browser.":"The Python host serves these actions in the current session.")+
      card("Copilot custom connector",config.tools.map(t=>fold(t.name,paragraph(t.purpose)+code(t.method+" "+t.path)+(t.detail&&t.detail!==t.purpose?paragraph(t.detail):""),t.method)).join("")+source("Open connector definition",BLUEPRINT+"openapi-entra.swagger.json"),"The connector schema defines "+config.tools.length+" operations for an approved organizational deployment.");
    case "workflows": return card("Presentation workflow",activeSteps().map((s,i)=>fold(s,paragraph(["The author supplies the topic, language, audience and requested length.","The agent returns candidate pages with source evidence. The author can ask for changes and inspect the updated order.","The author reviews the current plan and chooses to generate the presentation.","The agent produces an editable PPTX, source information and quality checks."][i]))).join(""))+
      card("Copilot Studio topic",config.steps.map(s=>fold(s.id.replaceAll("_"," "),code(JSON.stringify(s,null,2)),s.kind)).join("")+source("Open workflow blueprint",BLUEPRINT+"flow-design.json"),"Exact configured steps from the project’s topic blueprint.");
    case "hooks": return card("Application checks",configList([["Before a local request","Verify the session and applicable request limits."],["Before an optional model call","Reserve against host limits before contacting the model."],["During source selection","Keep traceable source pages and flag gaps."],["Before retrieval of a local output","Resolve the file in the authenticated session."]])+source("Open local HTTP implementation","scripts/serve_studio.py"))+
      card("Connector action constraints",Object.entries(config.toolConfiguration).map(([k,v])=>fold(k,code(typeof v==="string"?v:JSON.stringify(v,null,2)))).join(""),"The project records these settings for manual binding in Copilot Studio.");
    case "memory": return card("Conversation state",configList([["Scope",hosted?"Current browser session":"Current server session"],["Working brief","Topic, generation settings and ordered source selections"],["Revisions","Generated versions can be revisited from the chat."],["Source of truth","Evidence and original page references remain attached to the outline."]]))+
      card("Artifact access",'<p class="subtitle">'+e(hosted?"Downloads are produced in the visitor’s browser. A separate browser session has its own working state.":"The local host scopes version files and history to their session. The developer monitor exposes operational events and counters.")+'</p>'+source("Review session handling",hosted?"studio/browser-engine.js":"scripts/serve_studio.py"));
    case "evaluation": return card("Review a generated presentation",configList([["Source traceability","Match selected titles, evidence and page references to the source report."],["Completeness","Compare requested length with the actual number of supported pages."],["Document review","Inspect the editable deck, notes and visual layout in PowerPoint."],["Quality report","Use the QA download attached to the generated version."]])+'<a class="panel-link" href="index.html">Generate a test draft '+icon("arrow")+'</a>')+
      card("Repository verification",configList([["Retrieval","Index construction, freshness, selection and multilingual search terms"],["Export","Draft assembly, source notes, template replacement and layout checks"],["Runtime","Session boundaries, budget handling and release-specific acceptance"]])+source("Open measured test cases","docs/studio/evaluation.csv")+'<br>'+source("Inspect the local model comparison","docs/studio/model-comparison.json")+'<br>'+source("Browse project tests","https://github.com/ManlingXu/fao-amr-pptx-builder/tree/main/tests"),"Automated assertions and manual PowerPoint review cover different parts of the workflow.");
    case "monitor": {
      const ev=Array.isArray(dev.events)?dev.events:[];
      const mt=(k,v)=>'<div class="panel metric"><span>'+e(k)+'</span><b>'+e(val(v))+'</b></div>';
      const rows=ev.slice(0,30).map(x=>'<tr><td>'+e(x.time||"—")+'</td><td>'+e(x.action||"—")+'</td><td>'+e(x.outcome||"—")+'</td></tr>').join("");
      return '<div class="metrics">'+mt(hosted?"Browser sessions":"Host sessions",r.sessions)+mt("Model calls",u.model_calls)+mt("Tokens reserved",u.tokens_reserved)+'</div>'+
        card("Runtime limits",configList([["Requests per minute",l.requests_per_minute],["Model call ceiling",l.model_calls],["Reserved token ceiling",l.token_budget],["Runtime age",Number.isFinite(r.uptime_seconds)?Math.floor(r.uptime_seconds/60)+" min":"—"]]))+
        '<section class="panel"><div class="panel-actions"><h2>Recent activity</h2><button type="button" id="refresh" class="button">'+icon("refresh")+' Refresh</button></div><div id="refresh-status" class="statusmsg" role="status"></div>'+
        (ev.length?'<table class="event-table"><thead><tr><th>Time</th><th>Action</th><th>Outcome</th></tr></thead><tbody>'+rows+'</tbody></table>':'<p class="subtitle">No events are available for this runtime yet.</p>')+'</section>';
    }
    case "channels": return card("Available channels",configList([["Browser edition",hosted?"Active in this browser":"Standalone demo version"],["Teams-style web app","Presentation builder chat interface"],["Localhost",hosted?"Run the project locally":"This Python host"],["Shared tunnel",dev.deployment?.tunnel_enabled?"Enabled by host":"Start on a local host when shared access is needed"],["Microsoft Teams","Organizational rollout pending"]]))+
      card("Organizational channel",'<p class="subtitle">The organization’s maker configures the agent, shares it with the intended audience and verifies access in Teams. See the project’s setup sequence for the connector and publishing steps.</p>'+source("Open Copilot Studio setup","docs/COPILOT_STUDIO_EN.md"));
    case "deployment": return card("Current deployment",configList([["Edition",workspaceName()],["Agent UI","Teams mode and Developer mode"],["Organizational Teams publication","Pending tenant configuration and acceptance"]]))+
      card("Organizational requirements",configList([["Environment","Copilot Studio maker access, supported environment and approved capacity"],["Identity","Entra app registration, user access scope and role or group"],["Connectors and data","Approved custom connector and source/output SharePoint permissions"],["Runtime","Approved HTTPS API endpoint with persistent storage"],["Release","Approved audience, Teams distribution policy and two-user acceptance"]])+source("Open CSI requirements","docs/studio/CSI_REQUIREMENTS.md")+'<br>'+source("Open migration guide","docs/studio/MIGRATION.md"));
    default:return "";
  }
}

function renderNav() {
  let group="";
  const target=document.getElementById("section-list");
  if(!target)return;
  target.innerHTML=sections.filter(i=>i[1].toLowerCase().includes(filter.toLowerCase())).map(([id,name,key,g])=>{
    const heading=group!==g?'<div class="nav-group">'+e(g)+'</div>':"";
    group=g;
    return heading+'<a class="nav-link'+(id===current?' active" aria-current="page':'')+'" href="#'+id+'">'+icon(key)+e(name)+'</a>';
  }).join("")||'<div class="nav-empty">No matching sections.</div>';
}
function render() {
  const [id,label,key]=headerInfo(location.hash.slice(1));
  current=id;
  const tabId=id==="evaluation"?"evaluate":id==="monitor"?"monitor":"build";
  const tabs=[["build","Build","#overview"],["preview","Preview","index.html"],["evaluate","Evaluate","#evaluation"],["monitor","Monitor","#monitor"]];
  const manifestKey = id==="workflows" ? "workflow" : id;
  const setting=config.manifest?.[manifestKey];
  const handoff=setting && id!=="skills" ? card("Maker handoff",fold("Inspect the project configuration",code(JSON.stringify(setting,null,2)))+source("Open agent manifest",BLUEPRINT+"migration/agent-manifest.json")) : "";
  const content=id==="overview"?overview():'<div class="detail-head"><span class="icon-tile">'+icon(key)+'</span><h1>'+e(label)+'</h1><p>'+e(descriptions[id])+'</p></div><div class="detail-stack">'+dataSection(id)+handoff+'</div>';
  app.innerHTML='<div class="agent-bar"><div class="agent-title"><div class="ppt" aria-hidden="true"></div><div><strong>PPT Builder</strong><small>Presentation agent</small></div></div>'+
    '<nav class="tabs" aria-label="Agent experiences">'+tabs.map(([k,n,h])=>'<a class="tab '+(tabId===k?"active":"")+'" href="'+h+'">'+n+'</a>').join("")+'</nav>'+
    '<span class="role-label">'+icon(browserEdition?"book":"lock")+(browserEdition?"Demo configuration":"Developer access")+'</span></div>'+
    '<div class="mobile-nav">'+icon("menu")+'<label for="section-select">Section</label><select id="section-select">'+sections.map(([key,name])=>'<option value="'+key+'"'+(key===id?' selected':'')+'>'+e(name)+'</option>').join("")+'</select></div>'+
    '<div class="shell"><aside class="sidebar"><div class="side-wrap"><label class="search">'+icon("search")+'<input id="section-search" type="search" autocomplete="off" aria-label="Find a section" placeholder="Find a section" value="'+e(filter)+'"></label><nav id="section-list" aria-label="Agent configuration"></nav></div></aside>'+
    '<div class="work"><div class="content"><div class="crumb"><a href="#overview">PPT Builder</a>'+icon("chev")+'<span>'+e(label)+'</span></div>'+content+'</div></div></div>';
  document.title=label+" · PPT Builder Studio";
  renderNav();
  document.getElementById("section-select").addEventListener("change",event=>location.hash=event.target.value);
  document.getElementById("section-search").addEventListener("input",event=>{filter=event.target.value;renderNav()});
  document.getElementById("refresh")?.addEventListener("click",refresh);
  document.getElementById("environment").textContent=workspaceName();
}
function makeError(message,status){const error=new Error(message);error.status=status;return error}
async function api(method,path,payload) {
  if(browserEdition && typeof window.browserAPI==="function")return window.browserAPI(method,path,payload);
  if(browserEdition)throw makeError("The browser runtime could not be loaded.",503);
  const res=await fetch(path,{method,credentials:"same-origin",headers:{Accept:"application/json",...(payload?{"Content-Type":"application/json"}:{})},...(payload?{body:JSON.stringify(payload)}:{})});
  const json=await res.json().catch(()=>null);
  if(!res.ok)throw makeError(json?.error||json?.detail||"The host could not complete this request.",res.status);
  if(!json)throw makeError("The local host returned an unexpected response.",502);
  return json;
}
async function readRuntime(){
  const response = await api("GET", "/api/developer");
  if (!browserEdition || response.runtime) return response;
  return {
    ...response,
    runtime: {
      mode: "browser", provider: "offline", corpus: "Bundled public evidence",
      decks: response.stats?.decks, slides: response.stats?.slides, sessions: response.sessionCount,
    },
    limits: {model_calls: 0, token_budget: 0}, usage: {model_calls: 0, tokens_reserved: 0},
  };
}
async function refresh(){
  const status=document.getElementById("refresh-status"), btn=document.getElementById("refresh");
  if(btn)btn.disabled=true;
  if(status)status.textContent="Refreshing…";
  try{dev=await readRuntime();render();document.getElementById("refresh-status").textContent="Updated just now."}
  catch(err){if(err.status===401||err.status===403){gate();return}if(status)status.textContent=err.message;if(btn)btn.disabled=false}
}
function gate(){
  document.getElementById("environment").textContent="Local workspace";
  app.innerHTML='<div class="gate-wrap"><div class="panel gate"><span class="icon-tile">'+icon("lock")+'</span><h1>Developer access</h1><p>Enter the developer password shown on the host computer to inspect this workspace.</p><form id="access-form"><label for="password">Developer password</label><input id="password" name="password" type="password" required maxlength="256" autocomplete="current-password"><div id="login-error" class="err" role="alert"></div><button class="button primary" type="submit">Open workspace '+icon("arrow")+'</button></form></div></div>';
  document.getElementById("access-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const button=event.target.querySelector("button"),err=document.getElementById("login-error");
    button.disabled=true;err.textContent="";
    try{await api("POST","/api/login",{password:document.getElementById("password").value,role:"developer"});await loadWorkspace()}
    catch(error){err.textContent=error.message||"Unable to sign in.";button.disabled=false}
  });
}
function failure(err){
  app.innerHTML='<div class="gate-wrap"><div class="panel gate"><span class="icon-tile">'+icon("info")+'</span><h1>Workspace unavailable</h1><p>'+e(err.message)+'</p><button class="button primary" id="retry" type="button">Try again</button></div></div>';
  document.getElementById("retry").addEventListener("click",start);
}
async function loadWorkspace(){
  session=await api("GET","/api/session");
  if(!browserEdition && (!session.authenticated||session.role!=="developer")){gate();return}
  const conf=await fetch("studio-config.json",{credentials:"same-origin"});
  if(conf.status===401||conf.status===403){gate();return}
  if(!conf.ok)throw makeError("The project configuration could not be loaded.",conf.status);
  config=await conf.json();dev=await readRuntime();render();
}
async function start(){
  try{
    if(browserEdition&&typeof window.browserAPI!=="function")await import("./browser-engine.js");
    await loadWorkspace();
  }catch(err){if(!browserEdition&&(err.status===401||err.status===403))gate();else failure(err)}
}
document.querySelectorAll("[data-icon]").forEach(el=>el.innerHTML=icon(el.dataset.icon));
window.addEventListener("hashchange",()=>{if(config){render();window.scrollTo(0,0)}});
start();
