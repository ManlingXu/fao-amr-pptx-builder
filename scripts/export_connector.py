"""Export a Swagger 2 custom connector for the implemented tool API."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

def specification(base_url: str, auth: str, tenant_id: str, api_app_id: str) -> dict:
    url = urlsplit(base_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Use an HTTPS service base URL without credentials, query or fragment.")
    if auth not in {"api-key", "entra"}:
        raise ValueError("auth must be api-key or entra")
    slide = {"type": "object", "properties": {
        "slideId": {"type":"string"}, "deckName":{"type":"string"},
        "slideNumber":{"type":"integer"}, "title":{"type":"string"},
        "snippet":{"type":"string"}, "url":{"type":"string"},
        "effectiveYear":{"type":"integer","x-nullable":True},
        "reportDate":{"type":"string","x-nullable":True},
        "dateConfidence":{"type":"number"}, "dateReason":{"type":"string"},
        "sourceHash":{"type":"string"}, "freshness":{"type":"string"},
        "relatedVersions":{"type":"integer"}, "explanation":{"type":"array","items":{"type":"string"}}
    }}
    provenance = {"type":"object","properties":{
        "outputSlide":{"type":"integer"}, "slideId":{"type":"string"},
        "deckName":{"type":"string"}, "slideNumber":{"type":"integer"},
        "title":{"type":"string"}, "url":{"type":"string"},
        "reportDate":{"type":"string","x-nullable":True},
        "effectiveYear":{"type":"integer","x-nullable":True},
        "dateConfidence":{"type":"number"}, "dateReason":{"type":"string"},
        "sourceHash":{"type":"string"}
    }}
    slide_analysis = {"type":"object","properties":{
        **provenance["properties"],
        "wordCount":{"type":"integer"}, "occupancyRatio":{"type":"number"},
        "textShapeCount":{"type":"integer"}, "pictureCount":{"type":"integer"},
        "tableCount":{"type":"integer"}, "chartCount":{"type":"integer"},
        "groupCount":{"type":"integer"},
        "contentType":{"type":"string","enum":["title","text","image","table","chart","mixed"]},
        "density":{"type":"string","enum":["low","medium","high"]},
        "recommendedLayoutAction":{"type":"string","enum":["reuse","reflow","review"]}
    }}
    layout_issue = {"type":"object","properties":{
        "code":{"type":"string"},
        "severity":{"type":"string","enum":["warning","error"]},
        "reason":{"type":"string"},
        "shapeIndex":{"type":"integer","x-nullable":True},
        "shapeName":{"type":"string","x-nullable":True}
    }}
    layout_report = {"type":"object","properties":{
        "jobId":{"type":"string"}, "slideCount":{"type":"integer"},
        "slideWidth":{"type":"integer"}, "slideHeight":{"type":"integer"},
        "slides":{"type":"array","items":{"type":"object","properties":{
            "slideNumber":{"type":"integer"},
            "issues":{"type":"array","items":{"$ref":"#/definitions/LayoutIssue"}}
        }}},
        "summary":{"type":"object","properties":{
            "slides":{"type":"integer"}, "issues":{"type":"integer"},
            "errors":{"type":"integer"}, "warnings":{"type":"integer"},
            "slidesNeedingReview":{"type":"integer"}
        }},
        "limitations":{"type":"array","items":{"type":"string"}}
    }}
    template = {"type":"object","properties":{
        "templateId":{"type":"string","pattern":"^[0-9a-f]{32}$"},
        "fileName":{"type":"string"}, "slideWidth":{"type":"integer"},
        "slideHeight":{"type":"integer"},
        "layoutNames":{"type":"array","items":{"type":"string"}},
        "warnings":{"type":"array","items":{"type":"string"}}
    }}
    template_id = {"type":"string","minLength":32,"maxLength":32,"pattern":"^[0-9a-f]{32}$",
                   "description":"Exact templateId returned by UploadTemplate for this signed-in user"}
    job = {"type":"object","properties":{
        "jobId":{"type":"string"}, "status":{"type":"string","enum":["queued","running","completed","failed"]},
        "statusUrl":{"type":"string"}, "title":{"type":"string"},
        "downloadUrl":{"type":"string","x-nullable":True},
        "webUrl":{"type":"string","x-nullable":True}, "error":{"type":"string","x-nullable":True},
        "warnings":{"type":"array","items":{"type":"string"}},
        "sourceMap":{"type":"array","items":{"$ref":"#/definitions/SourceMapEntry"}},
        "template":{**template,"x-nullable":True},
        "sourceJobId":{"type":"string","x-nullable":True},
        "layoutOverrides":{"type":"array","items":{"type":"object","properties":{
            "outputSlide":{"type":"integer"},"layoutName":{"type":"string"}
        }}},
        "appliedLayouts":{"type":"array","items":{"type":"string"},"x-nullable":True}
    }}
    plan_proposed_section = {"type":"object","required":["title","query","slide_count"],
      "properties":{"title":{"type":"string","minLength":1,"maxLength":120},
        "query":{"type":"string","minLength":1,"maxLength":400},
        "slide_count":{"type":"integer","minimum":1,"maximum":8},
        "notes":{"type":"string","maxLength":600}}}
    plan_section = {"type":"object","properties":{
        "title":{"type":"string"},"query":{"type":"string"},
        "notes":{"type":"string"},"slideIds":{"type":"array","items":{"type":"string"}},
        "requestedSlides":{"type":"integer"},"gap":{"type":"boolean"}}}
    plan_request = {"type":"object","required":["title","audience","purpose","sections"],"properties":{
        "title":{"type":"string","minLength":1,"maxLength":120},
        "audience":{"type":"string","minLength":1,"maxLength":200},
        "purpose":{"type":"string","minLength":1,"maxLength":500},
        "sections":{"type":"array","minItems":1,"maxItems":8,
                    "items":{"$ref":"#/definitions/ProposedSection"}},
        "template_id":{**template_id,"x-nullable":True}}}
    revision_section = {"type":"object","required":["title","query"],"properties":{
        "title":{"type":"string","minLength":1,"maxLength":120},
        "query":{"type":"string","minLength":1,"maxLength":400},
        "slide_ids":{"type":"array","maxItems":20,
                    "items":{"type":"string","minLength":1,"maxLength":128}},
        "notes":{"type":"string","maxLength":600}}}
    revise_request = {"type":"object","required":["expected_revision","sections"],"properties":{
        "expected_revision":{"type":"integer","minimum":1},
        "sections":{"type":"array","minItems":1,"maxItems":8,
                    "items":{"$ref":"#/definitions/RevisionSection"}},
        "template_id":{**template_id,"x-nullable":True,
                       "description":"Omit to keep the current template, null to clear it"}}}
    finalize_request = {"type":"object","required":["expected_revision","confirmed"],"properties":{
        "expected_revision":{"type":"integer","minimum":1},
        "confirmed":{"type":"boolean","enum":[True],
                     "description":"Set only after explicit approval of this exact revision"}}}
    plan_result = {"type":"object","properties":{
        "planId":{"type":"string"},"revision":{"type":"integer"},
        "title":{"type":"string"},"audience":{"type":"string"},"purpose":{"type":"string"},
        "templateId":{**template_id,"x-nullable":True},
        "sections":{"type":"array","items":{"$ref":"#/definitions/PlanSection"}},
        "sourceMap":{"type":"array","items":{"$ref":"#/definitions/SourceMapEntry"}},
        "needsReview":{"type":"boolean"},"requiresUserConfirmation":{"type":"boolean"},
        "isReadyForDraft":{"type":"boolean"}}}
    if auth == "api-key":
        security = {"ApiKey":{"type":"apiKey","in":"header","name":"X-API-Key"}}
        requirement = [{"ApiKey":[]}]
    else:
        UUID(tenant_id); UUID(api_app_id)
        scope = "api://" + api_app_id + "/access_as_user"
        security = {"EntraOAuth":{
            "type":"oauth2","flow":"accessCode",
            "authorizationUrl":"https://login.microsoftonline.com/" + tenant_id + "/oauth2/v2.0/authorize",
            "tokenUrl":"https://login.microsoftonline.com/" + tenant_id + "/oauth2/v2.0/token",
            "scopes":{scope:"Use the approved Presentation Assistant API as the signed-in user",
                      "offline_access":"Maintain the signed-in connector connection with refresh tokens"}
        }}
        requirement = [{"EntraOAuth":[scope,"offline_access"]}]
    error = {"description":"Request rejected or operation failed","schema":{"type":"object"}}
    def operation(operation_id, summary, parameters, schema, status="200"):
        return {"operationId":operation_id,"summary":summary,"x-ms-summary":summary,
                "description":summary,"parameters":parameters,
                "responses":{status:{"description":"Success","schema":schema},"default":error}}
    search_request = {"type":"object","required":["query"],"properties":{
        "query":{"type":"string","minLength":1,"maxLength":1000},
        "limit":{"type":"integer","minimum":1,"maximum":15,"default":15},
        "latest_only":{"type":"boolean","default":True}
    }}
    draft_request = {"type":"object","required":["title","slide_ids","confirmed"],"properties":{
        "title":{"type":"string","minLength":1,"maxLength":120},
        "slide_ids":{"type":"array","minItems":1,"maxItems":20,"uniqueItems":True,"items":{"type":"string","minLength":1,"maxLength":128}},
        "confirmed":{"type":"boolean","enum":[True],"description":"True only after the user explicitly approves the ordered selection"},
        "template_id":{**template_id,"x-nullable":True}
    }}
    upload_request = {"type":"object","required":["file_name","content_base64"],"properties":{
        "file_name":{"type":"string","minLength":1,"maxLength":180,
                     "description":"Attachment file name ending in .pptx or .potx"},
        "content_base64":{"type":"string","minLength":1,"maxLength":22369624,
                          "description":"Base64 of the original binary file, bound from a File input; never fill with AI"}
    }}
    apply_request = {"type":"object","required":["template_id","confirmed"],"properties":{
        "template_id":template_id,
        "title":{"type":"string","minLength":1,"maxLength":120,"x-nullable":True},
        "confirmed":{"type":"boolean","enum":[True],
                     "description":"True only when user explicitly requests this template for this completed draft"},
        "layout_overrides":{"type":"array","maxItems":20,"items":{
            "$ref":"#/definitions/LayoutOverride"},
            "description":"Optional AI-selected exact layout name for each 1-based output slide"}
    }}
    analyze_request = {"type":"object","required":["slide_ids"],"properties":{
        "slide_ids":{"type":"array","minItems":1,"maxItems":20,"uniqueItems":True,
                     "items":{"type":"string","minLength":1,"maxLength":128}}
    }}
    layout_override = {"type":"object","required":["output_slide","layout_name"],"properties":{
        "output_slide":{"type":"integer","minimum":1,"maximum":20},
        "layout_name":{"type":"string","minLength":1,"maxLength":255}
    }}
    body=lambda schema:[{"name":"body","in":"body","required":True,"schema":schema}]
    path=lambda name:[{"name":name,"in":"path","required":True,"type":"string"}]
    return {
      "swagger":"2.0","info":{"title":"Presentation Assistant","version":"1.3.0",
      "description":"Search and structurally analyze source slides, plan and revise storylines, confirm drafts, apply exact template layouts and review layout risks."},
      "host":url.netloc,"basePath":url.path.rstrip("/") or "/","schemes":["https"],
      "consumes":["application/json"],"produces":["application/json"],
      "securityDefinitions":security,"security":requirement,
      "paths":{
        "/api/search":{"post":operation("SearchSlides","Search approved source slides",body(search_request),
          {"type":"object","properties":{"query":{"type":"string"},"results":{"type":"array","items":{"$ref":"#/definitions/Slide"}}}})},
        "/api/slides/analyze":{"post":operation("AnalyzeSlides","Inspect selected slide structure before layout decisions",body(analyze_request),
          {"type":"object","properties":{"slides":{"type":"array","items":{"$ref":"#/definitions/SlideAnalysis"}},"limitations":{"type":"array","items":{"type":"string"}}}})},
        "/api/slides/{slide_id}/versions":{"get":operation("GetSlideVersions","Inspect related source versions",path("slide_id"),
          {"type":"object","properties":{"slideId":{"type":"string"},"versions":{"type":"array","items":{"$ref":"#/definitions/Slide"}}}})},
        "/api/templates":{"post":operation("UploadTemplate","Upload a chat attachment as a PowerPoint template",body(upload_request),{"$ref":"#/definitions/Template"},"201")},
        "/api/drafts/{job_id}/template":{"post":operation("ApplyTemplate","Apply an uploaded template to a completed draft",path("job_id")+body(apply_request),{"$ref":"#/definitions/Job"},"202")},
        "/api/plans":{"post":operation("PlanPresentation","Propose a structured storyline grounded in approved slide searches",body(plan_request),{"$ref":"#/definitions/Plan"},"201")},
        "/api/plans/{plan_id}":{
          "get":operation("GetPresentationPlan","Retrieve the current owner-scoped storyline and revision",path("plan_id"),{"$ref":"#/definitions/Plan"}),
          "put":operation("RevisePresentationPlan","Replace sections and ordered slide IDs using a known revision",path("plan_id")+body(revise_request),{"$ref":"#/definitions/Plan"})},
        "/api/plans/{plan_id}/draft":{
          "post":operation("CreateDraftFromPlan","Create a PPT after confirming an exact storyline revision",path("plan_id")+body(finalize_request),{"$ref":"#/definitions/Job"},"202")},
        "/api/drafts":{"post":operation("CreateDraft","Create a draft after user confirmation",body(draft_request),{"$ref":"#/definitions/Job"},"202")},
        "/api/drafts/{job_id}":{"get":operation("GetDraftStatus","Check draft status and file link",path("job_id"),{"$ref":"#/definitions/Job"})},
        "/api/drafts/{job_id}/layout-report":{"get":operation("GetLayoutReport","Review heuristic layout risks in a completed draft",path("job_id"),{"$ref":"#/definitions/LayoutReport"})}
      },
      "definitions":{"Slide":slide,"SourceMapEntry":provenance,"Job":job,"Template":template,
                     "ProposedSection":plan_proposed_section,"RevisionSection":revision_section,
                     "PlanSection":plan_section,"Plan":plan_result,
                     "SlideAnalysis":slide_analysis,"LayoutIssue":layout_issue,
                     "LayoutReport":layout_report,"LayoutOverride":layout_override}
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--base-url",default="https://api.example.invalid")
    parser.add_argument("--auth",choices=["api-key","entra"],default="api-key")
    parser.add_argument("--tenant-id",default="00000000-0000-0000-0000-000000000000")
    parser.add_argument("--api-app-id",default="00000000-0000-0000-0000-000000000000")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    data=specification(args.base_url,args.auth,args.tenant_id,args.api_app_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Wrote",args.output)
    if ".invalid" in data["host"]:
        print("Template host only: regenerate with the CSI-approved HTTPS address before import.")

if __name__=="__main__":
    main()
