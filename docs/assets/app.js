/* ==========================================================
   TITO SENTINEL — 共享交互脚本
   关键原则：GSAP 是锦上添花，不是必需品。
   如果 CDN 没加载成功（网络问题/被挡），页面内容必须依然完整可见，
   不能因为一个脚本报错就让整页看起来是空白的。
   ========================================================== */
(function(){
  const HAS_GSAP = (typeof gsap !== 'undefined');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (HAS_GSAP) {
    // 只有确认 GSAP 真的加载成功了，才给 html 加上这个 class，
    // CSS 里 .reveal 的"先隐藏再动画"效果是靠这个 class 才生效的。
    document.documentElement.classList.add('js-anim-ready');
    if (typeof ScrollTrigger !== 'undefined') gsap.registerPlugin(ScrollTrigger);
  } else {
    console.warn('[Tito] GSAP 未加载成功，已回退为静态显示（内容仍然完整可见，只是没有动画）。');
  }

  // 小工具：把一段代码包起来，就算这一小块坏了，也不会连累其他功能
  function safe(fn){
    try { fn(); } catch (e) { console.warn('[Tito] 某个动效模块出错，已跳过：', e); }
  }

  /* ---------- 标题波浪基线（呼应 Tito 波浪轮廓的签名细节） ---------- */
  safe(function(){
    if (!HAS_GSAP) return;
    function wrapCharsInNode(node){
      if(node.nodeType===3){
        const frag=document.createDocumentFragment();
        node.textContent.split('').forEach(ch=>{
          if(ch.trim()===''){frag.appendChild(document.createTextNode(ch));return;}
          const span=document.createElement('span');
          span.className='wchar';span.textContent=ch;
          frag.appendChild(span);
        });
        node.replaceWith(frag);
      }else if(node.nodeType===1 && node.tagName!=='BR'){
        Array.from(node.childNodes).forEach(wrapCharsInNode);
      }
    }
    document.querySelectorAll('h2.wavy').forEach(h=>{
      Array.from(h.childNodes).forEach(wrapCharsInNode);
      const chars = h.querySelectorAll('.wchar');
      chars.forEach((c,i)=>{
        const wave = Math.sin(i*0.7)*7;
        gsap.set(c,{y:wave,rotation:wave*0.35});
      });
    });
  });

  /* ---------- HERO 标题逐字入场（只有存在 #heroTitle 的页面才跑） ---------- */
  safe(function(){
    const heroTitle = document.getElementById('heroTitle');
    if(!heroTitle) return;
    heroTitle.querySelectorAll('.word').forEach(word=>{
      word.innerHTML = word.textContent.split('').map(c=>`<span class="char">${c}</span>`).join('');
    });
    if(HAS_GSAP && !reduced){
      const tl = gsap.timeline({defaults:{ease:'power4.out'}});
      if(document.getElementById('dittoWrap')){
        tl.from('#dittoWrap',{y:60,opacity:0,scale:.7,duration:1,ease:'back.out(1.6)'});
      }
      tl.from('#heroTitle .char',{yPercent:120,duration:.9,stagger:.045},'-=0.5')
        .to('.hero .reveal',{opacity:1,y:0,duration:.8,stagger:.15},'-=0.4');
    }
  });

  /* ---------- Tito 呼吸浮动 + 眨眼 + 声波（首页大 ditto） ---------- */
  safe(function(){
    if(!HAS_GSAP || reduced) return;
    if(!document.getElementById('dittoWrap')) return;
    gsap.to('#dittoBody',{y:-10,duration:2.2,yoyo:true,repeat:-1,ease:'sine.inOut'});
    gsap.to('#dittoShadow',{scaleX:.85,transformOrigin:'center',duration:2.2,yoyo:true,repeat:-1,ease:'sine.inOut'});
    gsap.to('#dittoEyes',{scaleY:.08,transformOrigin:'center 96px',duration:.09,yoyo:true,repeat:1,repeatDelay:.05,
      delay:2,onComplete:function blinkLoop(){
        gsap.to('#dittoEyes',{scaleY:.08,transformOrigin:'center 96px',duration:.09,yoyo:true,repeat:1,
          delay:1.8+Math.random()*3,onComplete:blinkLoop});
      }});
    gsap.timeline({repeat:-1,repeatDelay:1.4})
      .fromTo('.sound-arc',{opacity:0,x:-8},{opacity:1,x:0,duration:.4,stagger:.18})
      .to('.sound-arc',{opacity:0,duration:.5,delay:.5});
    const ex = gsap.quickTo('#dittoEyes','x',{duration:.4,ease:'power3'});
    const ey = gsap.quickTo('#dittoEyes','y',{duration:.4,ease:'power3'});
    window.addEventListener('mousemove',e=>{
      const nx=(e.clientX/innerWidth-.5)*10, ny=(e.clientY/innerHeight-.5)*8;
      ex(nx); ey(ny);
    });
  });

  /* ---------- Marquee 无缝滚动（跑马灯，若页面没有则跳过） ---------- */
  safe(function(){
    const inner=document.getElementById('marqueeInner');
    if(!inner) return;
    inner.innerHTML += inner.innerHTML + inner.innerHTML;
    if(HAS_GSAP && !reduced){
      gsap.to(inner,{xPercent:-33.333,duration:18,ease:'none',repeat:-1});
    }
  });

  /* ---------- 滚动 reveal（通用淡入） ---------- */
  safe(function(){
    if(!HAS_GSAP) return;
    gsap.utils.toArray('.reveal').forEach(el=>{
      if(reduced){gsap.set(el,{opacity:1,y:0});return;}
      gsap.to(el,{
        opacity:1,y:0,duration:.9,ease:'power3.out',
        scrollTrigger:{trigger:el,start:'top 85%'}
      });
    });
  });

  /* ---------- 大数字填充（why.html / index.html 用） ---------- */
  safe(function(){
    const fillEl = document.getElementById('bigNumFill');
    if(!fillEl) return;
    if(HAS_GSAP && !reduced){
      gsap.to(fillEl,{
        clipPath:'inset(0% 0 0 0)',duration:1.4,ease:'power3.inOut',
        scrollTrigger:{trigger:'#bigNum',start:'top 75%'}
      });
    }else{
      gsap.set ? gsap.set(fillEl,{clipPath:'inset(0% 0 0 0)'}) : (fillEl.style.clipPath='inset(0% 0 0 0)');
    }
  });

  /* ---------- 三道防线卡片入场（defense.html / index.html 用） ---------- */
  safe(function(){
    const stops = document.querySelectorAll('.stops .scene-stop');
    if(!stops.length) return;
    if(HAS_GSAP && !reduced && typeof ScrollTrigger !== 'undefined'){
      ScrollTrigger.batch('.stops .scene-stop',{
        start:'top 85%',
        onEnter:b=>gsap.to(b,{opacity:1,y:0,duration:.8,stagger:.14,ease:'power3.out'})
      });
      const pathEl = document.querySelector('.scene-path path');
      if(pathEl){
        gsap.fromTo(pathEl,{opacity:0},{opacity:.6,duration:1.2,ease:'power2.out',
          scrollTrigger:{trigger:'.defense-scene',start:'top 75%'}});
      }
    }else{
      stops.forEach(s=>{ s.style.opacity=1; });
    }
  });

  /* ---------- Tito 客串小彩蛋：全站反复出现的浮动摇摆 ---------- */
  safe(function(){
    if(!HAS_GSAP || reduced) return;
    document.querySelectorAll('.ditto-cameo').forEach((el,i)=>{
      gsap.to(el,{y:-8,rotation:'+=4',duration:2.4+i*.3,yoyo:true,repeat:-1,ease:'sine.inOut',transformOrigin:'center'});
    });
  });

  /* ---------- 聊天气泡弹出（speak.html / index.html 用） ---------- */
  safe(function(){
    const bubble = document.getElementById('chatBubble');
    if(!bubble) return;
    if(HAS_GSAP){
      gsap.to(bubble,{
        opacity:1,y:0,scale:1,duration:.7,ease:'back.out(1.7)',
        scrollTrigger: typeof ScrollTrigger!=='undefined' ? {trigger:bubble,start:'top 85%'} : undefined
      });
    }else{
      bubble.style.opacity=1;bubble.style.transform='none';
    }
  });

  /* ---------- 磁性按钮 ---------- */
  safe(function(){
    if(!HAS_GSAP || reduced || !matchMedia('(pointer:fine)').matches) return;
    document.querySelectorAll('.magnetic').forEach(btn=>{
      const bx=gsap.quickTo(btn,'x',{duration:.35,ease:'power3'});
      const by=gsap.quickTo(btn,'y',{duration:.35,ease:'power3'});
      btn.addEventListener('mousemove',e=>{
        const r=btn.getBoundingClientRect();
        bx((e.clientX-r.left-r.width/2)*.35);
        by((e.clientY-r.top-r.height/2)*.35);
      });
      btn.addEventListener('mouseleave',()=>{bx(0);by(0);});
    });
  });

  /* ---------- Hero 背景视差 ---------- */
  safe(function(){
    if(!HAS_GSAP || reduced || typeof ScrollTrigger==='undefined') return;
    if(!document.querySelector('.hero')) return;
    gsap.to('.blob-a',{y:120,scrollTrigger:{trigger:'.hero',start:'top top',end:'bottom top',scrub:1}});
    gsap.to('.blob-b',{y:-90,scrollTrigger:{trigger:'.hero',start:'top top',end:'bottom top',scrub:1}});
  });

  /* ---------- 预约演示表单（demo.html 专用，纯前端原型，不会真的发送数据） ---------- */
  safe(function(){
    const form = document.getElementById('demoForm');
    if(!form) return;
    form.addEventListener('submit', function(e){
      e.preventDefault();
      form.style.display='none';
      const success = document.getElementById('formSuccess');
      if(success) success.classList.add('show');
    });
  });

})();
