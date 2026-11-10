(() => {
  const $ = (id) => document.getElementById(id);
  const state = { endpoint: localStorage.getItem("jassim_endpoint") || "https://jassim-ai-core-final-production.up.railway.app", token: sessionStorage.getItem("jassim_token") || "", conversation: "web-" + Math.random().toString(36).slice(2,10), connected: false, health: null, activeController: null };
  $("conversationId").textContent = state.conversation;
  function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
  function setStatus(ok,label){state.connected=ok;$("connectionLabel").textContent=label;$("sideStatus").textContent=label;$("chatConnection").textContent=label;document.querySelectorAll(".live-dot").forEach(x=>x.classList.toggle("online",ok));$("apiStat").textContent=ok?"متصل":"غير متصل";$("apiDetail").textContent=ok?"تم فحص /health بنجاح":"تحقق من عنوان الخادم";$("step1").textContent=ok?"✓":"●"}
  function openSettings(){$("endpoint").value=state.endpoint;$("accountEmail").value="";$("accountPassword").value="";$("accountStatus").textContent=state.token?"هناك جلسة حساب محفوظة في علامة التبويب هذه.":"سجّل الدخول أو أنشئ حساباً. لا تحتاج إلى رمز الخادم.";$("logoutAccount").disabled=!state.token;$("settingsDialog").showModal()}
  async function request(path,options={}){if(!state.endpoint)throw new Error("أدخل عنوان الخادم أولاً");const url=state.endpoint.replace(/\/$/,"")+path;const response=await fetch(url,{...options,headers:{"Content-Type":"application/json",...(state.token?{"Authorization":"Bearer "+state.token}:{}),...(options.headers||{})}});if(!response.ok)throw new Error("HTTP "+response.status);return response.json()}
  async function checkHealth(){if(!state.endpoint){setStatus(false,"لم يتم إعداد الخادم");$("engineStat").textContent="غير معروف";$("storageStat").textContent="—";return}try{const h=await request("/health");state.health=h;setStatus(!!h.ok,h.ok?"الخادم متصل":"الخادم غير جاهز");if($("imageStatus"))$("imageStatus").textContent=h.image_generation_ready?"توليد الصور جاهز · "+(h.image_model||"FLUX"):"الخادم متصل، لكن توليد الصور ينتظر ضبط JASSIM_HF_TOKEN في Railway.";$("engineStat").textContent=h.model||h.engine||"غير معروف";$("engineDetail").textContent=h.model_ready?"النموذج جاهز للطلبات":(h.ollama_reachable?"Ollama متصل لكن النموذج غير محمّل":"محرك Ollama غير متاح");$("storageStat").textContent=h.storage||"غير معروف";$("checkedStat").textContent=new Date().toLocaleTimeString("ar-TN");$("systemEngine").textContent=h.engine||"غير معروف";$("systemStorage").textContent=h.storage||"غير معروف";$("serverUrlText").textContent=state.endpoint}catch(e){setStatus(false,"تعذر الاتصال");$("apiDetail").textContent=e.message;toast("فشل فحص الخادم: "+e.message)}}
  function addBubble(text,who){const box=document.createElement("div");box.className="bubble "+who;box.textContent=text; $("messages").appendChild(box); $("messages").scrollTop=$("messages").scrollHeight;return box}
  function showView(id){document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===id));document.querySelectorAll(".nav").forEach(x=>x.classList.toggle("active",x.dataset.view===id));const names={overview:"نظرة عامة",chat:"مركز المحادثة",memory:"الذاكرة والسجل",images:"استوديو الصور",systems:"الخادم والمحركات"};$("pageTitle").textContent=names[id]||"JASSIM AI"}
  document.querySelectorAll(".nav").forEach(b=>b.addEventListener("click",()=>showView(b.dataset.view)));
  document.querySelectorAll("[data-open]").forEach(b=>b.addEventListener("click",()=>showView(b.dataset.open)));
  $("settingsBtn").addEventListener("click",openSettings);$("heroConnect").addEventListener("click",openSettings);$("systemSettings").addEventListener("click",openSettings);$("refreshBtn").addEventListener("click",checkHealth);
  $("settingsForm").addEventListener("submit",async e=>{if(e.submitter&&e.submitter.id==="saveEndpoint"){e.preventDefault();const value=$("endpoint").value.trim().replace(/\/$/,"");if(!/^https:\/\//i.test(value)){toast("استخدم رابط HTTPS الآمن");return}state.endpoint=value;localStorage.setItem("jassim_endpoint",value);$("settingsDialog").close();await checkHealth()}});
  async function authenticateAccount(mode){
    const email=$("accountEmail").value.trim(),password=$("accountPassword").value;
    if(!email||password.length<10){toast("أدخل بريداً صحيحاً وكلمة مرور من 10 أحرف على الأقل");return}
    const button=$(mode==="register"?"registerAccount":"loginAccount");button.disabled=true;
    try{
      const response=await fetch(state.endpoint.replace(/\/$/,"")+"/api/auth/"+mode,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||("HTTP "+response.status));
      if(!data.token||!data.token.startsWith("jss_"))throw new Error("لم يُرجع الخادم رمز جلسة صالحاً");
      state.token=data.token;sessionStorage.setItem("jassim_token",state.token);
      $("settingsDialog").close();toast(mode==="register"?"تم إنشاء الحساب بنجاح":"تم تسجيل الدخول");await checkHealth();
    }catch(error){toast("تعذر إتمام العملية: "+error.message)}
    finally{button.disabled=false}
  }
  $("loginAccount").addEventListener("click",()=>authenticateAccount("login"));
  $("registerAccount").addEventListener("click",()=>authenticateAccount("register"));
  $("logoutAccount").addEventListener("click",async()=>{
    if(!state.token)return;
    try{
      const result=await request("/api/auth/logout",{method:"POST",body:"{}"});
      if(!result.revoked)throw new Error("لم يؤكد الخادم إبطال الجلسة");
      state.token="";sessionStorage.removeItem("jassim_token");
      toast("تم تسجيل الخروج وإبطال الجلسة");openSettings();
    }catch(error){
      if(error.message==="HTTP 401"){
        state.token="";sessionStorage.removeItem("jassim_token");
        toast("الجلسة منتهية أو ملغاة بالفعل");openSettings();
      }else{
        toast("تعذر تأكيد تسجيل الخروج؛ احتفظنا بالجلسة لإعادة المحاولة: "+error.message);
      }
    }
  });
  $("chatForm").addEventListener("submit",async e=>{
    e.preventDefault();
    if(state.activeController){state.activeController.abort();return}
    const message=$("chatInput").value.trim();if(!message)return;
    $("chatInput").value="";addBubble(message,"user");
    if(!state.endpoint){addBubble("اربط خادم JASSIM من زر الإعدادات أولاً.","ai");return}
    const btn=e.submitter||$("chatForm").querySelector('button[type="submit"]');
    const controller=new AbortController();state.activeController=controller;
    btn.disabled=false;btn.textContent="إيقاف ■";btn.classList.add("stop-active");
    const answerBubble=addBubble("","ai");let received=false,done=false;
    try{
      const response=await fetch(state.endpoint.replace(/[/]+$/,"")+"/api/chat/stream",{
        method:"POST",signal:controller.signal,
        headers:{"Content-Type":"application/json","Accept":"text/event-stream","Authorization":"Bearer "+state.token},
        body:JSON.stringify({message,conversation_id:state.conversation})
      });
      if(!response.ok)throw new Error("HTTP "+response.status);
      if(!response.body)throw new Error("المتصفح لا يدعم البث المباشر");
      const reader=response.body.getReader(),decoder=new TextDecoder("utf-8");let buffer="";
      while(true){
        const part=await reader.read();if(part.done)break;
        buffer+=decoder.decode(part.value,{stream:true});let boundary;
        while((boundary=buffer.indexOf("\n\n"))>=0){
          const block=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);
          const data=block.split(/\r?\n/).filter(line=>line.startsWith("data:")).map(line=>line.slice(5).trim()).join("\n");
          if(!data)continue;let event;try{event=JSON.parse(data)}catch(_){continue}
          if(event.type==="token"){answerBubble.textContent+=event.token||"";received=true;$("messages").scrollTop=$("messages").scrollHeight}
          else if(event.type==="done"){done=true;if(event.engine){$("engineStat").textContent=event.engine;$("engineDetail").textContent="المحرك المستخدم في آخر رد"}}
          else if(event.type==="error")throw new Error(event.error||"generation_failed");
        }
      }
      if(!received)answerBubble.textContent=done?"اكتمل الطلب دون نص.":"انتهى الاتصال دون وصول رد.";
    }catch(err){
      if(err.name==="AbortError")answerBubble.textContent=received?answerBubble.textContent+"\n\n[تم إيقاف التوليد]":"تم إيقاف التوليد.";
      else answerBubble.textContent=(received?answerBubble.textContent+"\n\n":"")+"تعذر إكمال الرد: "+err.message;
    }finally{state.activeController=null;btn.textContent="إرسال ↑";btn.classList.remove("stop-active");btn.disabled=false}
  });
  $("clearChat").addEventListener("click",()=>{state.conversation="web-"+Math.random().toString(36).slice(2,10);$("conversationId").textContent=state.conversation;$("messages").innerHTML="";const w=document.createElement("div");w.className="welcome";w.innerHTML="<div class='welcome-icon'>✳</div><b>بدأت محادثة جديدة</b><p>اكتب رسالتك للمتابعة.</p>";$("messages").appendChild(w)});
  $("generateImage").addEventListener("click",async()=>{
    const prompt=$("imagePrompt").value.trim();if(!prompt){toast("اكتب وصف الصورة أولاً");return}
    if(!state.endpoint||!state.token){toast("اربط الخادم وأدخل رمز الوصول أولاً");return}
    const btn=$("generateImage"),status=$("imageStatus"),result=$("imageResult");
    btn.disabled=true;btn.textContent="جارٍ التوليد…";status.textContent="قد يستغرق التوليد بعض الوقت.";result.innerHTML="";
    try{
      const data=await request("/api/images/generate",{method:"POST",body:JSON.stringify({prompt})});
      if(!data.image_base64||!["image/png","image/jpeg","image/webp"].includes(String(data.mime_type||"").toLowerCase()))throw new Error("أعاد مزود الصور صيغة غير مدعومة");
      const img=document.createElement("img");img.alt="الصورة التي أنشأها JASSIM AI";img.src="data:"+data.mime_type+";base64,"+data.image_base64;result.appendChild(img);
      const extension={"image/png":"png","image/jpeg":"jpg","image/webp":"webp"}[data.mime_type.toLowerCase()];
      const link=document.createElement("a");link.href=img.src;link.download="jassim-ai-image."+extension;link.textContent="تنزيل الصورة";link.className="secondary image-download";result.appendChild(link);
      status.textContent="تم التوليد بواسطة "+data.model;
    }catch(e){status.textContent="تعذر التوليد: "+e.message;toast("فشل توليد الصورة")}
    finally{btn.disabled=false;btn.textContent="توليد الصورة ✦"}
  });
  $("loadHistory").addEventListener("click",async()=>{try{const h=await request("/api/history?conversation_id="+encodeURIComponent(state.conversation));$("historyOutput").textContent=JSON.stringify(h,null,2)}catch(e){$("historyOutput").textContent="تعذر تحميل السجل: "+e.message}});
  $("serverUrlText").textContent=state.endpoint||"لم يتم الإعداد";checkHealth();
  if(!state.token)openSettings();
})();