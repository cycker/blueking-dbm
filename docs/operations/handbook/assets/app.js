/* ============================================================
 * MongoDB Handbook · 公共脚本
 * - 注入侧边栏（数据驱动）
 * - 注入顶部栏 + 搜索 + 主题
 * - 注入页脚 + 上下页导航
 * - Tabs / Copy-code 等通用组件
 * ============================================================ */

(function(){
  // 章节注册表 —— 单一数据源，所有页面共用
  const CHAPTERS = [
    { id:'home',    href:'../index.html',                 num:'',   title:'手册首页' },
    { id:'ch01',    href:'01-concepts.html',              num:'1',  title:'核心概念与术语' },
    { id:'ch02',    href:'02-cluster-topology.html',      num:'2',  title:'集群拓扑与节点规范' },
    { id:'ch03',    href:'03-first-deploy.html',          num:'3',  title:'第一次部署' },
    { id:'ch04',    href:'04-tickets.html',               num:'4',  title:'单据系统（Tickets）' },
    { id:'ch05',    href:'05-mongosh.html',               num:'5',  title:'mongosh 使用指南' },
    { id:'ch06',    href:'06-bk-dbmon.html',              num:'6',  title:'bk-dbmon 监控与备份' },
    { id:'ch07',    href:'07-versions.html',              num:'7',  title:'MongoDB 版本支持' },
    { id:'ch08',    href:'08-mongo-tools.html',           num:'8',  title:'MongoDB 工具集' },
    { id:'ch09',    href:'09-mongodb-logs.html',          num:'9',  title:'MongoDB 日志' },
    { id:'ch10',    href:'10-indexes.html',               num:'10', title:'MongoDB 索引设计与优化' },
    { id:'ch11',    href:'11-uri-readpref.html',          num:'11', title:'URI 与 Read Preference' },
    { id:'ch12',    href:'12-cases.html',                 num:'12', title:'真实业务案例' },
    { id:'ch13',    href:'13-performance-views.html',     num:'13', title:'DBM 性能视图（Grafana）' },
    { id:'ch14',    href:'14-dbha-autofix.html',          num:'14', title:'DBHA 与故障自愈' },
    { id:'ch15',    href:'15-appendix.html',              num:'15', title:'附录 · 排障 / FAQ' },
  ];
  window.HANDBOOK_CHAPTERS = CHAPTERS;

  // 工具：根据当前页面是否为 index.html 调整 href
  function fixHref(href, fromIndex){
    if (fromIndex){
      // 在 handbook/index.html 上：home 指向自身，其他章节指向 chapters/xx
      if (href.startsWith('../')) return '#';
      return 'chapters/' + href;
    }
    // 在 handbook/chapters/xx.html 页面上：保持相对路径不变
    return href;
  }

  // 为章节链接附加 deck=1（用于跨章保持 PPT 模式）
  function withDeckParam(href){
    const [baseAndQuery, hash = ''] = href.split('#');
    const [base, query = ''] = baseAndQuery.split('?');
    const params = new URLSearchParams(query);
    params.set('deck', '1');
    const qs = params.toString();
    const out = qs ? `${base}?${qs}` : base;
    return hash ? `${out}#${hash}` : out;
  }

  // 注入顶部栏
  function renderTopbar(opts){
    const fromIndex = !!opts.fromIndex;
    const homeHref = fromIndex ? '#' : '../index.html';
    const html = `
      <div class="topbar-inner">
        <div class="flex items-center gap-12">
          <button class="menu-toggle" id="menuToggle" aria-label="菜单">☰</button>
          <a class="brand" href="${homeHref}" style="text-decoration:none;color:inherit">
            <div class="logo">M</div>
            <div>
              MongoDB Handbook
              <small>蓝鲸 DBM · 中文运维手册</small>
            </div>
          </a>
        </div>
        <div class="top-actions">
          <div class="top-search">
            <span>🔍</span>
            <input id="globalSearch" placeholder="在本页搜索..." />
          </div>
          <a class="btn ghost" href="${homeHref}">🏠 首页</a>
          <button class="btn primary" id="printBtn">🖨 打印</button>
        </div>
      </div>`;
    const bar = document.createElement('header');
    bar.className = 'topbar';
    bar.innerHTML = html;
    document.body.insertBefore(bar, document.body.firstChild);

    document.getElementById('printBtn').onclick = ()=>window.print();
    document.getElementById('menuToggle').onclick = ()=>{
      document.querySelector('.sidebar')?.classList.toggle('show');
    };
    // 页内文字搜索高亮
    const inp = document.getElementById('globalSearch');
    inp.addEventListener('input', e=>highlightSearch(e.target.value.trim()));
    inp.addEventListener('keydown', e=>{
      if (e.key === 'Escape') { inp.value=''; highlightSearch(''); }
    });
  }

  // 注入侧边栏
  function renderSidebar(activeId, fromIndex){
    const list = CHAPTERS.map(c=>{
      const href = fixHref(c.href, fromIndex);
      const cls = (c.id === activeId) ? ' class="active"' : '';
      const num = c.num || '🏠';
      return `<li><a href="${href}"${cls}><span class="num">${num}</span><span>${c.title}</span></a></li>`;
    }).join('');
    const html = `
      <h4>📖 章节导航</h4>
      <ul class="sidebar-list">${list}</ul>
      <h4>🧭 本章目录</h4>
      <ul class="sidebar-list" id="localToc"></ul>
      <h4>🔗 外部参考</h4>
      <ul class="sidebar-list">
        <li><a href="https://www.mongodb.com/docs/manual/" target="_blank" rel="noopener"><span class="num">📚</span><span>MongoDB Manual</span></a></li>
        <li><a href="https://www.mongodb.com/docs/mongodb-shell/" target="_blank" rel="noopener"><span class="num">🐚</span><span>mongosh 文档</span></a></li>
        <li><a href="https://www.mongodb.com/docs/manual/release-notes/" target="_blank" rel="noopener"><span class="num">📝</span><span>Release Notes</span></a></li>
      </ul>`;
    const sb = document.querySelector('.sidebar');
    if (sb){
      sb.innerHTML = html;
      buildLocalToc();
    }
  }

  // 本章目录（基于 .section h2）
  function buildLocalToc(){
    const toc = document.getElementById('localToc');
    if (!toc) return;
    const sections = document.querySelectorAll('.section[id]');
    if (!sections.length){toc.innerHTML='<li style="padding:8px 12px;color:#64748b;font-size:12.5px">无</li>';return;}
    toc.innerHTML = Array.from(sections).map(s=>{
      const h2 = s.querySelector('h2');
      const ix = h2?.querySelector('.ix')?.textContent || '·';
      const title = h2 ? Array.from(h2.childNodes).filter(n=>n.nodeType===3 || (n.nodeType===1 && !n.classList.contains('ix') && !n.classList.contains('pill'))).map(n=>n.textContent).join('').trim() : s.id;
      return `<li><a href="#${s.id}"><span class="num">${ix}</span><span>${title}</span></a></li>`;
    }).join('');
  }

  // 注入上下页导航
  function renderPager(activeId, fromIndex){
    if (activeId === 'home') return;
    const idx = CHAPTERS.findIndex(c=>c.id===activeId);
    if (idx <= 0) return;
    const prev = CHAPTERS[idx-1];
    const next = CHAPTERS[idx+1];
    const main = document.querySelector('.main');
    if (!main) return;
    const pager = document.createElement('div');
    pager.className = 'pager';
    pager.innerHTML = `
      ${prev ? `<a href="${fixHref(prev.href, fromIndex)}" class="prev">
        <div class="arrow">←</div>
        <div><div class="lbl">上一篇</div><div class="ttl">${prev.num ? '第 '+prev.num+' 章 · ' : ''}${prev.title}</div></div>
      </a>` : '<div></div>'}
      ${next ? `<a href="${fixHref(next.href, fromIndex)}" class="next">
        <div><div class="lbl">下一篇</div><div class="ttl">${next.num ? '第 '+next.num+' 章 · ' : ''}${next.title}</div></div>
        <div class="arrow">→</div>
      </a>` : '<div></div>'}`;
    main.appendChild(pager);
  }

  // 页脚
  function renderFooter(){
    const f = document.createElement('footer');
    f.className = 'footer';
    f.innerHTML = `📄 来源：<code>docs/operations/handbook-md/*.md</code> · 🛠 蓝鲸 DBM · MongoDB 入门与运维手册 · 由 With 整理生成`;
    document.body.appendChild(f);
  }

  // Tabs 组件
  function bindTabs(){
    document.querySelectorAll('[data-tabs]').forEach(group=>{
      const tabs = group.querySelectorAll('.tab');
      const panels = group.querySelectorAll('.tab-panel');
      tabs.forEach((t,i)=>{
        t.addEventListener('click',()=>{
          tabs.forEach(x=>x.classList.remove('active'));
          panels.forEach(x=>x.classList.remove('active'));
          t.classList.add('active');
          panels[i]?.classList.add('active');
        });
      });
      tabs[0]?.classList.add('active');
      panels[0]?.classList.add('active');
    });
  }

  // 复制按钮注入到 <pre>
  function injectCopy(){
    document.querySelectorAll('pre').forEach(pre=>{
      if (pre.dataset.copy === '0') return;
      const tag = pre.querySelector('.code-tag');
      const btn = document.createElement('button');
      btn.className='code-tag';
      btn.style.cursor='pointer';btn.style.userSelect='none';
      btn.style.right = tag ? '70px' : '10px';
      btn.textContent='📋 复制';
      btn.onclick = ()=>{
        const text = pre.querySelector('code')?.innerText || pre.innerText;
        navigator.clipboard?.writeText(text).then(()=>{
          btn.textContent='✓ 已复制';
          setTimeout(()=>btn.textContent='📋 复制',1500);
        });
      };
      pre.appendChild(btn);
    });
  }

  // 页内搜索高亮
  let _hlNodes = [];
  function clearHL(){
    _hlNodes.forEach(n=>{
      const p = n.parentNode;
      if (p){p.replaceChild(document.createTextNode(n.textContent), n); p.normalize();}
    });
    _hlNodes = [];
  }
  function highlightSearch(kw){
    clearHL();
    if (!kw || kw.length < 2) return;
    const main = document.querySelector('.main');
    if (!main) return;
    const re = new RegExp(kw.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {
      acceptNode(node){
        if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        if (['SCRIPT','STYLE','PRE','CODE'].includes(node.parentNode.nodeName)) return NodeFilter.FILTER_REJECT;
        return re.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    const targets = [];
    let n; while ((n=walker.nextNode())) targets.push(n);
    targets.forEach(node=>{
      const span = document.createElement('span');
      span.innerHTML = node.nodeValue.replace(re, m=>`<mark style="background:linear-gradient(120deg,#fde68a,#fbbf24);color:#0b1220;padding:0 2px;border-radius:3px">${m}</mark>`);
      const frag = document.createDocumentFragment();
      Array.from(span.childNodes).forEach(c=>frag.appendChild(c));
      const wrapper = document.createElement('span');
      wrapper.dataset.hl='1';
      wrapper.appendChild(frag);
      node.parentNode.replaceChild(wrapper, node);
      _hlNodes.push(wrapper);
    });
    // 滚到第一个
    const first = main.querySelector('mark');
    first?.scrollIntoView({behavior:'smooth',block:'center'});
  }

  // ========================================================
  // 🎬 PPT / Slide Deck 模式
  //   - 章节页：把每个 .section 自动包成一张 slide（content 版式）
  //   - 增加封面页 + 章末页
  //   - 键盘 ←/→/Space/PageUp/PageDown/Home/End/F/Esc/数字
  // ========================================================
  function buildDeckForChapter(activeId){
    const main = document.querySelector('.main');
    if (!main) return null;
    const meta = CHAPTERS.find(c=>c.id===activeId);
    const chapterIndex = CHAPTERS.findIndex(c=>c.id===activeId);
    const nextChapter = chapterIndex >= 0 ? CHAPTERS[chapterIndex + 1] : null;
    const nextHref = nextChapter ? withDeckParam(fixHref(nextChapter.href, false)) : '';
    const title = main.querySelector('.page-title')?.textContent?.trim() || (meta?.title || '');
    const lead  = main.querySelector('.page-lead')?.textContent?.trim() || '';
    const sections = Array.from(main.querySelectorAll('.section'));

    const deck = document.createElement('div');
    deck.className = 'deck';
    const stage = document.createElement('div');
    stage.className = 'deck-stage';
    deck.appendChild(stage);

    // 封面
    const cover = document.createElement('div');
    cover.className = 'slide chapter-cover';
    cover.innerHTML = `
      <div class="slide-tag">CHAPTER · 第 ${meta?.num || ''} 章</div>
      <div class="ch-num">${meta?.num || ''}</div>
      <h1 class="slide-title">${title}</h1>
      <p class="slide-sub">${lead || '蓝鲸 DBM · MongoDB 入门与运维手册'}</p>
      <div class="slide-foot">
        <span class="brand-mini"><span class="dot"></span>MongoDB Handbook</span>
        <span>使用 ← → 翻页 · 按 ESC 退出</span>
      </div>`;
    stage.appendChild(cover);

    // 内容页：默认每个 .section 一页；若 section 内有多个 h3，则自动拆分多页
    sections.forEach((sec, i)=>{
      const h2 = sec.querySelector(':scope > h2');
      const children = Array.from(sec.children);
      const h3Indexes = children
        .map((el, idx) => ({ el, idx }))
        .filter(x => x.el.tagName === 'H3')
        .map(x => x.idx);

      const parts = [];
      if (!h3Indexes.length) {
        parts.push({
          title: '',
          nodes: children.filter(el => el !== h2),
        });
      } else {
        const contentStart = h2 ? children.indexOf(h2) + 1 : 0;
        const firstH3 = h3Indexes[0];
        if (firstH3 > contentStart) {
          parts.push({
            title: '概览',
            nodes: children.slice(contentStart, firstH3),
          });
        }
        h3Indexes.forEach((startIdx, idx2) => {
          const endIdx = idx2 + 1 < h3Indexes.length ? h3Indexes[idx2 + 1] : children.length;
          const h3 = children[startIdx];
          parts.push({
            title: h3?.textContent?.trim() || `子节 ${idx2 + 1}`,
            nodes: children.slice(startIdx, endIdx),
          });
        });
      }

      parts.forEach((part, partIdx) => {
        const slide = document.createElement('div');
        slide.className = 'slide content';
        const secClone = document.createElement('section');
        secClone.className = sec.className || 'section';
        if (sec.id) secClone.id = sec.id + (parts.length > 1 ? `-p${partIdx + 1}` : '');
        if (h2) secClone.appendChild(h2.cloneNode(true));
        part.nodes.forEach(node => secClone.appendChild(node.cloneNode(true)));

        const partMark = parts.length > 1 ? ` · 分页 ${partIdx + 1}/${parts.length}` : '';
        const partTitle = parts.length > 1 ? ` · ${part.title}` : '';
        slide.innerHTML = `
          <div class="slide-tag">第 ${meta?.num || ''} 章 · ${i+1}/${sections.length}${partMark}${partTitle}</div>
          <div class="slide-body"></div>
          <div class="slide-foot">
            <span class="brand-mini"><span class="dot"></span>${title}</span>
            <span>← / → 翻页</span>
          </div>`;
        slide.querySelector('.slide-body').appendChild(secClone);
        stage.appendChild(slide);
      });
    });

    // 章末
    const outro = document.createElement('div');
    outro.className = 'slide outro';
    outro.innerHTML = `
      <div>
        <div class="slide-tag" style="text-align:center">END OF CHAPTER ${meta?.num || ''}</div>
        <div class="big">Thanks!</div>
        ${nextChapter ? `
          <a class="deck-next-link" href="${nextHref}">
            <span>下一章</span>
            <strong>第 ${nextChapter.num} 章 · ${nextChapter.title}</strong>
            <i>→</i>
          </a>` : `
          <div class="deck-next-link disabled">
            <span>已到最后一章</span>
            <strong>返回手册首页或退出 PPT 模式</strong>
          </div>`}
        <p class="slide-sub" style="text-align:center;margin-top:18px">按 <kbd style="background:#0c1730;border:1px solid var(--border);padding:2px 8px;border-radius:6px;color:#a5f3fc;font-family:JetBrains Mono,monospace">ESC</kbd> 返回阅读模式　·　按 <kbd style="background:#0c1730;border:1px solid var(--border);padding:2px 8px;border-radius:6px;color:#a5f3fc;font-family:JetBrains Mono,monospace">Home</kbd> 回到首页</p>
      </div>`;
    stage.appendChild(outro);

    return deck;
  }

  function deckMount(deckEl){
    const slides = Array.from(deckEl.querySelectorAll('.slide'));
    if (!slides.length) return;
    document.body.classList.add('deck-mode');
    document.body.appendChild(deckEl);
    try { sessionStorage.setItem('handbook_deck_autostart', '1'); } catch(_){}

    // 进度条
    const prog = document.createElement('div');
    prog.className = 'deck-progress';
    prog.innerHTML = '<i></i>';
    document.body.appendChild(prog);

    // 控制条
    const ctrl = document.createElement('div');
    ctrl.className = 'deck-controls';
    ctrl.innerHTML = `
      <button class="ctrl" data-act="first" title="首页 (Home)">⏮</button>
      <button class="ctrl" data-act="prev" title="上一页 (←)">◀</button>
      <span class="num"><b id="dkCur">1</b> / <span id="dkTot">${slides.length}</span></span>
      <button class="ctrl" data-act="next" title="下一页 (→)">▶</button>
      <button class="ctrl" data-act="last" title="末页 (End)">⏭</button>
      <span class="sep"></span>
      <button class="ctrl" data-act="mobile" title="切换移动/桌面模式">📱</button>
      <button class="ctrl" data-act="full" title="全屏 (F)">⛶</button>
      <button class="ctrl" data-act="exit" title="退出 (Esc)">✕</button>`;
    document.body.appendChild(ctrl);

    // 缩略图
    const thumbs = document.createElement('div');
    thumbs.className = 'deck-thumbs';
    thumbs.innerHTML = slides.map((_,i)=>`<span class="thumb" data-i="${i}"><span class="tip">${i+1}/${slides.length}</span></span>`).join('');
    document.body.appendChild(thumbs);

    // 提示
    const hint = document.createElement('div');
    hint.className = 'deck-hint';
    hint.innerHTML = `<kbd>←</kbd><kbd>→</kbd> 翻页 · <kbd>Space</kbd> 下一页 · <kbd>F</kbd> 全屏 · <kbd>Esc</kbd> 退出`;
    document.body.appendChild(hint);

    // 主题切换器
    const THEMES = [
      { id:'aurora',  name:'Aurora · 极光科技' },
      { id:'frost',   name:'Frost · 浅色玻璃' },
      { id:'morandi', name:'Morandi · 莫兰迪' },
      { id:'lumen',   name:'Lumen · 暖阳商务' },
      { id:'sunset',  name:'Sunset · 暮色暗夜' },
    ];
    const savedTheme = (function(){
      try { return localStorage.getItem('handbook_deck_theme') || 'aurora'; } catch(_){ return 'aurora'; }
    })();
    document.body.setAttribute('data-theme', savedTheme);
    const themer = document.createElement('div');
    themer.className = 'deck-theme';
    themer.innerHTML = `
      <span class="lbl">Theme</span>
      ${THEMES.map(t => `<span class="swatch${t.id===savedTheme?' active':''}" data-theme="${t.id}"><span class="tip">${t.name}</span></span>`).join('')}
    `;
    document.body.appendChild(themer);
    themer.addEventListener('click', e => {
      const sw = e.target.closest('.swatch'); if (!sw) return;
      const id = sw.dataset.theme;
      document.body.setAttribute('data-theme', id);
      themer.querySelectorAll('.swatch').forEach(el => el.classList.toggle('active', el === sw));
      try { localStorage.setItem('handbook_deck_theme', id); } catch(_){}
    });

    let cur = 0;
    const goto = (i)=>{
      i = Math.max(0, Math.min(slides.length-1, i));
      slides.forEach((s,idx)=>s.classList.toggle('active', idx===i));
      thumbs.querySelectorAll('.thumb').forEach((t,idx)=>t.classList.toggle('active', idx===i));
      document.getElementById('dkCur').textContent = i+1;
      prog.querySelector('i').style.width = ((i+1)/slides.length*100).toFixed(2) + '%';
      cur = i;
    };
    const next = ()=>goto(cur+1);
    const prev = ()=>goto(cur-1);

    ctrl.addEventListener('click', e=>{
      const b = e.target.closest('button[data-act]'); if (!b) return;
      const act = b.dataset.act;
      if (act==='next') next();
      else if (act==='prev') prev();
      else if (act==='first') goto(0);
      else if (act==='last') goto(slides.length-1);
      else if (act==='mobile'){
        const on = document.body.classList.toggle('deck-mobile');
        b.textContent = on ? '🖥' : '📱';
        b.title = on ? '切回桌面模式' : '切换移动/桌面模式';
        try{ localStorage.setItem('handbook_deck_mobile', on ? '1' : '0'); }catch(_){}
      }
      else if (act==='full'){
        if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
        else document.exitFullscreen?.();
      } else if (act==='exit') deckUnmount();
    });
    thumbs.addEventListener('click', e=>{
      const t = e.target.closest('.thumb'); if (!t) return;
      goto(parseInt(t.dataset.i,10));
    });

    // 键盘
    const onKey = (e)=>{
      if (['INPUT','TEXTAREA'].includes(document.activeElement?.tagName)) return;
      switch(e.key){
        case 'ArrowRight':
        case 'PageDown':
        case ' ': next(); e.preventDefault(); break;
        case 'ArrowLeft':
        case 'PageUp': prev(); e.preventDefault(); break;
        case 'Home': goto(0); e.preventDefault(); break;
        case 'End': goto(slides.length-1); e.preventDefault(); break;
        case 'Escape': deckUnmount(); break;
        case 'f':
        case 'F':
          if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
          else document.exitFullscreen?.();
          break;
        default:
          if (/^[0-9]$/.test(e.key)){
            const n = parseInt(e.key,10);
            if (n>=1 && n<=slides.length) goto(n-1);
          }
      }
    };
    window._deckOnKey = onKey;
    document.addEventListener('keydown', onKey);

    // 鼠标滚轮翻页（节流）
    let wheelLock = 0;
    const onWheel = (e)=>{
      const now = Date.now();
      if (now - wheelLock < 700) return;
      // 仅当当前 slide.body 没有滚动空间时才翻页
      const body = slides[cur].querySelector('.slide-body');
      if (body){
        if (e.deltaY > 0 && body.scrollTop + body.clientHeight < body.scrollHeight - 4) return;
        if (e.deltaY < 0 && body.scrollTop > 4) return;
      }
      wheelLock = now;
      if (e.deltaY > 0) next(); else prev();
    };
    deckEl.addEventListener('wheel', onWheel, {passive:true});
    window._deckOnWheel = onWheel;

    // 触屏滑动
    let tx=0;
    deckEl.addEventListener('touchstart', e=>{tx = e.changedTouches[0].clientX});
    deckEl.addEventListener('touchend', e=>{
      const dx = e.changedTouches[0].clientX - tx;
      if (Math.abs(dx) > 40){ if (dx<0) next(); else prev(); }
    });

    // 📱 移动模式：自动检测 + 左右点击热区 + 持久化
    const stage = deckEl.querySelector('.deck-stage');
    const tapL = document.createElement('div');
    tapL.className = 'deck-tap left';
    tapL.innerHTML = '<span class="arrow">‹</span>';
    tapL.addEventListener('click', e=>{ e.stopPropagation(); prev(); });
    const tapR = document.createElement('div');
    tapR.className = 'deck-tap right';
    tapR.innerHTML = '<span class="arrow">›</span>';
    tapR.addEventListener('click', e=>{ e.stopPropagation(); next(); });
    stage?.appendChild(tapL); stage?.appendChild(tapR);

    // 自动判定移动端：宽 ≤ 768 或 触屏 + 窄屏；也可由 localStorage 强制
    const mobileBtn = ctrl.querySelector('[data-act="mobile"]');
    function applyMobile(on){
      document.body.classList.toggle('deck-mobile', !!on);
      if (mobileBtn){
        mobileBtn.textContent = on ? '🖥' : '📱';
        mobileBtn.title = on ? '切回桌面模式' : '切换移动/桌面模式';
      }
    }
    let saved = null;
    try{ saved = localStorage.getItem('handbook_deck_mobile'); }catch(_){}
    if (saved === '1') applyMobile(true);
    else if (saved === '0') applyMobile(false);
    else {
      const isMobile = window.matchMedia('(max-width:768px)').matches
        || (('ontouchstart' in window) && window.innerWidth < 900);
      applyMobile(isMobile);
    }

    // 进入移动模式后短暂显示翻页热区提示，1.6s 自动隐藏
    if (document.body.classList.contains('deck-mobile')){
      tapL.classList.add('show'); tapR.classList.add('show');
      setTimeout(()=>{ tapL.classList.remove('show'); tapR.classList.remove('show'); }, 1600);
    }

    // 监听窗口尺寸变化（如旋转屏幕）：用户没手动设置过才自动切
    const onResize = ()=>{
      let userSet = null;
      try{ userSet = localStorage.getItem('handbook_deck_mobile'); }catch(_){}
      if (userSet === '1' || userSet === '0') return;
      const isMobile = window.matchMedia('(max-width:768px)').matches;
      if (isMobile !== document.body.classList.contains('deck-mobile')){
        applyMobile(isMobile);
      }
    };
    window.addEventListener('resize', onResize);
    window._deckOnResize = onResize;

    goto(0);
  }

  function deckUnmount(){
    document.body.classList.remove('deck-mode');
    document.body.classList.remove('deck-mobile');
    document.body.removeAttribute('data-theme');
    document.querySelector('.deck')?.remove();
    document.querySelector('.deck-progress')?.remove();
    document.querySelector('.deck-controls')?.remove();
    document.querySelector('.deck-thumbs')?.remove();
    document.querySelector('.deck-hint')?.remove();
    document.querySelector('.deck-exit')?.remove();
    document.querySelector('.deck-theme')?.remove();
    try { sessionStorage.removeItem('handbook_deck_autostart'); } catch(_){}
    if (window._deckOnKey) document.removeEventListener('keydown', window._deckOnKey);
    if (window._deckOnResize){ window.removeEventListener('resize', window._deckOnResize); window._deckOnResize = null; }
    if (document.fullscreenElement) document.exitFullscreen?.();
  }

  // 章节页 / 首页底部右下角的 PPT 启动按钮
  function injectDeckLaunch(activeId){
    const btn = document.createElement('button');
    btn.className = 'deck-launch';
    btn.innerHTML = '🎬 进入 PPT 模式';
    btn.title = '以幻灯片方式浏览本章 (按 P 也可启动)';
    const launchDeck = ()=>{
      // 如果是首页（自定义 deck 已经在 DOM 中），则用 page 自带的 deck
      const existing = document.querySelector('#homeDeck');
      let deck;
      if (existing){
        deck = existing.cloneNode(true);
        deck.id = '';
      } else {
        deck = buildDeckForChapter(activeId);
      }
      if (!deck) return;
      deckMount(deck);
    };
    btn.onclick = launchDeck;
    document.body.appendChild(btn);

    // 按 P 快捷启动
    document.addEventListener('keydown', e=>{
      if (['INPUT','TEXTAREA'].includes(document.activeElement?.tagName)) return;
      if (document.body.classList.contains('deck-mode')) return;
      if (e.key==='p' || e.key==='P'){ btn.click(); }
    });

    // 通过 ?deck=1 或会话标记进入页面时自动进入 PPT 模式
    const sp = new URLSearchParams(window.location.search);
    let fromSession = false;
    try { fromSession = sessionStorage.getItem('handbook_deck_autostart') === '1'; } catch(_){}
    if ((sp.get('deck') === '1' || fromSession) && !document.body.classList.contains('deck-mode')){
      launchDeck();
    }
  }

  // 自动初始化
  window.HandbookInit = function(opts){
    opts = opts || {};
    renderTopbar(opts);
    renderSidebar(opts.activeId || 'home', !!opts.fromIndex);
    renderPager(opts.activeId || 'home', !!opts.fromIndex);
    renderFooter();
    bindTabs();
    injectCopy();
    injectDeckLaunch(opts.activeId || 'home');
  };

  // 暴露给首页直接调用（首页有自己的 #homeDeck 模板）
  window.DeckMount = deckMount;
  window.DeckUnmount = deckUnmount;
})();
