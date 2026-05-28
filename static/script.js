/* ─── Canvas Spark System ──────────────────────────── */
class SparkSystem {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.particles = [];
    this.lastScrollY = window.scrollY;
    this.scrollVelocity = 0;
    this.resize();
    this.spawnBase(40);
    window.addEventListener('resize', () => this.resize());
    window.addEventListener('scroll', () => this.onScroll(), { passive: true });
    this.animate();
  }

  resize() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  onScroll() {
    const dy = Math.abs(window.scrollY - this.lastScrollY);
    this.lastScrollY = window.scrollY;
    this.scrollVelocity = Math.min(dy, 60);
    const count = Math.floor(this.scrollVelocity * 0.6);
    if (count > 0) this.spawnBase(count);
  }

  spawnBase(count) {
    for (let i = 0; i < count; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: this.canvas.height * 0.7 + Math.random() * (this.canvas.height * 0.35),
        vx: (Math.random() - 0.5) * 1.2,
        vy: -(Math.random() * 2.2 + 0.4),
        life: 1,
        decay: Math.random() * 0.006 + 0.003,
        size: Math.random() * 2.2 + 0.4,
        hue: Math.random() * 40 + 15,
      });
    }
  }

  spawnBurst(x, y, count) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Math.random() * 3 + 1;
      this.particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 2,
        life: 1,
        decay: Math.random() * 0.015 + 0.01,
        size: Math.random() * 3 + 1,
        hue: Math.random() * 40 + 15,
      });
    }
  }

  update() {
    this.particles = this.particles.filter(p => p.life > 0.01);
    for (const p of this.particles) {
      p.x += p.vx;
      p.y += p.vy;
      p.vy -= 0.01;
      p.vx += (Math.random() - 0.5) * 0.08;
      p.life -= p.decay;
    }
    if (this.particles.length < 35) this.spawnBase(4);
  }

  draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    for (const p of this.particles) {
      ctx.save();
      ctx.globalAlpha = Math.min(p.life * 0.8, 0.8);
      const color = `hsl(${p.hue}, 100%, 60%)`;
      ctx.shadowBlur = 8;
      ctx.shadowColor = color;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }

  animate() {
    this.update();
    this.draw();
    requestAnimationFrame(() => this.animate());
  }
}

/* ─── Web Audio Metal Stamp ───────────────────────── */
let audioCtx = null;

function getAudioCtx() {
  if (!audioCtx) {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (Ctor) audioCtx = new Ctor();
  }
  return audioCtx;
}

function playStampSound() {
  const ctx = getAudioCtx();
  if (!ctx) return;

  const dur = 0.18;
  const sr = ctx.sampleRate;
  const buf = ctx.createBuffer(1, Math.floor(sr * dur), sr);
  const data = buf.getChannelData(0);

  for (let i = 0; i < data.length; i++) {
    const t = i / sr;
    const env = Math.exp(-t * 50);
    const ring = Math.sin(2 * Math.PI * 1800 * t) * 0.3;
    data[i] = ((Math.random() * 2 - 1) * 0.7 + ring) * env;
  }

  const src = ctx.createBufferSource();
  src.buffer = buf;

  const hp = ctx.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.value = 1200;

  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.55, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);

  src.connect(hp);
  hp.connect(gain);
  gain.connect(ctx.destination);
  src.start();
  src.stop(ctx.currentTime + 0.25);
}

/* ─── DOM Sparks ──────────────────────────────────── */
function spawnClickSparks(clientX, clientY) {
  const layer = document.getElementById('sparks-layer');
  const count = 14;
  for (let i = 0; i < count; i++) {
    const s = document.createElement('div');
    s.className = 'click-spark';
    const angle = (i / count) * Math.PI * 2 + (Math.random() - 0.5) * 0.5;
    const dist = Math.random() * 55 + 20;
    s.style.left = clientX + 'px';
    s.style.top = clientY + 'px';
    s.style.setProperty('--tx', (Math.cos(angle) * dist) + 'px');
    s.style.setProperty('--ty', (Math.sin(angle) * dist) + 'px');
    s.style.animationDuration = (Math.random() * 0.2 + 0.4) + 's';
    layer.appendChild(s);
    s.addEventListener('animationend', () => s.remove(), { once: true });
  }
}

/* ─── Build embed HTML ────────────────────────────── */
function buildEmbed(url, thumb, title) {
  return `<a href="${url}"><img src="${thumb}" alt="${title.replace(/"/g, '&quot;')}"></a>`;
}

/* ─── Copy handler ────────────────────────────────── */
function stampFeedback(btn, event) {
  const textEl = btn.querySelector('.btn-text');
  btn.classList.add('stamped');
  textEl.textContent = 'STAMPED!';
  playStampSound();
  spawnClickSparks(event.clientX, event.clientY);
  if (sparkSystem) {
    const rect = btn.getBoundingClientRect();
    sparkSystem.spawnBurst(rect.left + rect.width / 2, rect.top + rect.height / 2, 18);
  }
  setTimeout(() => {
    btn.classList.remove('stamped');
    textEl.textContent = 'COPY EMBED';
  }, 2200);
}

function recordCopy(btn) {
  fetch('/api/copy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: btn.dataset.url }),
  }).then(r => r.json()).then(json => {
    if (!json.ok) return;
    const countEl = btn.closest('.card-body').querySelector('.copy-count');
    if (countEl) countEl.textContent = `${json.copies} cop${json.copies === 1 ? 'y' : 'ies'}`;
    setTotal(json.total);
  }).catch(() => {});
}

function handleCopy(btn, event) {
  const { url, thumb, title } = btn.dataset;
  const html = buildEmbed(url, thumb, title);

  /* Write rich HTML so email clients paste a rendered clickable image */
  if (navigator.clipboard && window.ClipboardItem) {
    const blob = new Blob([html], { type: 'text/html' });
    navigator.clipboard.write([new ClipboardItem({ 'text/html': blob })])
      .then(() => { stampFeedback(btn, event); recordCopy(btn); })
      .catch(() => {
        /* fallback for browsers without clipboard API */
        const ta = document.createElement('textarea');
        ta.value = html;
        ta.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
        stampFeedback(btn, event);
        recordCopy(btn);
      });
  } else {
    const ta = document.createElement('textarea');
    ta.value = html;
    ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    stampFeedback(btn, event);
    recordCopy(btn);
  }
}

/* ─── Notes / Change Requests ────────────────────── */
function relativeTime(ts) {
  const diff = Math.floor(Date.now() / 1000) - ts;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function updateNotesBtnState(btn, openCount) {
  btn.classList.toggle('pending', openCount > 0);
  btn.classList.toggle('clear', openCount === 0);
  btn.querySelector('.notes-text').textContent = openCount > 0 ? 'CHANGES REQUESTED' : 'REQUEST CHANGES';
  let badge = btn.querySelector('.notes-badge');
  if (openCount > 0) {
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'notes-badge';
      btn.appendChild(badge);
    }
    badge.textContent = openCount;
  } else if (badge) {
    badge.remove();
  }
}

function buildNoteItem(c) {
  const item = document.createElement('div');
  item.className = 'note-item' + (c.done ? ' done' : '');
  item.dataset.id = c.id;
  const who = c.author ? escHtml(c.author) : 'Anonymous';
  const tc = c.timecode ? `<span class="note-timecode">@ ${escHtml(c.timecode)}</span>` : '';
  item.innerHTML = `
    <div class="note-meta">${who}${tc ? ' &middot; ' + tc : ''} &middot; ${relativeTime(c.ts)}</div>
    <div class="note-text">${escHtml(c.text)}</div>
    <div class="note-actions">
      <button class="note-done-btn">${c.done ? '&#8617; REOPEN' : '&#10003; DONE'}</button>
      <button class="note-delete-btn">&#10005;</button>
    </div>
  `;
  return item;
}

function renderComments(listEl, comments) {
  listEl.innerHTML = '';
  const open = comments.filter(c => !c.done);
  const done = comments.filter(c => c.done);

  if (open.length === 0 && done.length === 0) {
    listEl.innerHTML = '<p class="notes-empty">No notes yet.</p>';
    return;
  }

  open.forEach(c => listEl.appendChild(buildNoteItem(c)));

  if (done.length > 0) {
    const toggle = document.createElement('button');
    toggle.className = 'resolved-toggle';
    toggle.dataset.expanded = '0';
    toggle.textContent = `Show resolved (${done.length})`;
    listEl.appendChild(toggle);

    const resolvedGroup = document.createElement('div');
    resolvedGroup.className = 'resolved-group';
    resolvedGroup.hidden = true;
    done.forEach(c => resolvedGroup.appendChild(buildNoteItem(c)));
    listEl.appendChild(resolvedGroup);
  }
}

async function toggleNotes(btn) {
  const panel = btn.nextElementSibling;
  const isOpen = panel.classList.contains('open');
  panel.classList.toggle('open', !isOpen);

  if (!isOpen && !panel.dataset.loaded) {
    const url = btn.dataset.url;
    try {
      const resp = await fetch(`/api/comments?url=${encodeURIComponent(url)}`);
      const json = await resp.json();
      if (json.ok) {
        renderComments(panel.querySelector('.notes-list'), json.comments);
        panel.dataset.loaded = '1';
      }
    } catch (e) {}
  }
}

async function toggleNoteDone(doneBtn) {
  const item = doneBtn.closest('.note-item');
  const id = item.dataset.id;
  const panel = doneBtn.closest('.notes-panel');
  const notesBtn = panel.previousElementSibling;
  const url = notesBtn.dataset.url;

  try {
    await fetch(`/api/comments/${id}`, { method: 'PATCH' });
    const resp = await fetch(`/api/comments?url=${encodeURIComponent(url)}`);
    const json = await resp.json();
    if (json.ok) {
      renderComments(panel.querySelector('.notes-list'), json.comments);
      updateNotesBtnState(notesBtn, json.open);
    }
  } catch (e) {}
}

async function deleteNote(deleteBtn) {
  const item = deleteBtn.closest('.note-item');
  const id = item.dataset.id;
  const panel = deleteBtn.closest('.notes-panel');
  const notesBtn = panel.previousElementSibling;
  const url = notesBtn.dataset.url;

  try {
    await fetch(`/api/comments/${id}`, { method: 'DELETE' });
    const resp = await fetch(`/api/comments?url=${encodeURIComponent(url)}`);
    const json = await resp.json();
    if (json.ok) {
      renderComments(panel.querySelector('.notes-list'), json.comments);
      updateNotesBtnState(notesBtn, json.open);
    }
  } catch (e) {}
}

function toggleResolved(toggleBtn) {
  const group = toggleBtn.nextElementSibling;
  const isExpanded = toggleBtn.dataset.expanded === '1';
  group.hidden = isExpanded;
  toggleBtn.dataset.expanded = isExpanded ? '0' : '1';
  const count = group.querySelectorAll('.note-item').length;
  toggleBtn.textContent = isExpanded ? `Show resolved (${count})` : 'Hide resolved';
}

async function addComment(form) {
  const panel = form.closest('.notes-panel');
  const notesBtn = panel.previousElementSibling;
  const url = notesBtn.dataset.url;
  const textEl = form.querySelector('.notes-input');
  const text = textEl.value.trim();
  const author = form.querySelector('.notes-author').value.trim();
  const timecode = form.querySelector('.notes-timecode').value.trim();
  if (!text) return;

  const submitBtn = form.querySelector('.notes-submit');
  submitBtn.disabled = true;
  submitBtn.textContent = 'ADDING…';

  try {
    const resp = await fetch('/api/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, text, author, timecode }),
    });
    const json = await resp.json();
    if (!json.ok) throw new Error(json.error);

    textEl.value = '';
    const resp2 = await fetch(`/api/comments?url=${encodeURIComponent(url)}`);
    const json2 = await resp2.json();
    if (json2.ok) {
      renderComments(panel.querySelector('.notes-list'), json2.comments);
      updateNotesBtnState(notesBtn, json2.open);
      panel.dataset.loaded = '1';
    }
  } catch (e) {
    console.error(e);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'ADD NOTE';
  }
}

/* ─── Render videos ───────────────────────────────── */
function renderYearSection(group, isFirst) {
  const section = document.createElement('section');
  section.className = 'year-section' + (isFirst ? ' open' : '');
  section.dataset.year = group.year;

  const header = document.createElement('button');
  header.className = 'year-header';
  header.setAttribute('aria-expanded', isFirst ? 'true' : 'false');
  header.innerHTML = `
    <span class="year-label">${group.year}</span>
    <span class="year-count">${group.videos.length} video${group.videos.length !== 1 ? 's' : ''}</span>
    <span class="year-arrow">&#9660;</span>
  `;

  const body = document.createElement('div');
  body.className = 'year-body';

  const grid = document.createElement('div');
  grid.className = 'video-grid';

  for (const v of group.videos) {
    const card = document.createElement('article');
    card.className = 'video-card';

    const thumbHtml = v.thumbnail
      ? `<img src="${escHtml(v.thumbnail)}" alt="${escHtml(v.title)}" loading="lazy">`
      : `<div class="no-thumb">&#9654;</div>`;

    const copies = v.copies || 0;
    const openComments = v.open_comments || 0;
    card.innerHTML = `
      <div class="thumb-wrap">
        ${thumbHtml}
        <div class="thumb-overlay">
          <a class="play-link" href="${escHtml(v.url)}" target="_blank" rel="noopener noreferrer">&#9654; VIEW</a>
        </div>
      </div>
      <div class="card-body">
        <h3 class="video-title">${escHtml(v.title)}</h3>
        <span class="copy-count">${copies} cop${copies === 1 ? 'y' : 'ies'}</span>
        <button class="copy-btn"
          data-url="${escHtml(v.url)}"
          data-thumb="${escHtml(v.thumbnail || '')}"
          data-title="${escHtml(v.title)}">
          <span class="btn-icon">&#10697;</span>
          <span class="btn-text">COPY EMBED</span>
        </button>
        <button class="notes-btn ${openComments > 0 ? 'pending' : 'clear'}" data-url="${escHtml(v.url)}">
          <span class="notes-icon">&#9998;</span>
          <span class="notes-text">${openComments > 0 ? 'CHANGES REQUESTED' : 'REQUEST CHANGES'}</span>
          ${openComments > 0 ? `<span class="notes-badge">${openComments}</span>` : ''}
        </button>
        <div class="notes-panel">
          <div class="notes-list"></div>
          <form class="notes-form">
            <input class="notes-author" type="text" placeholder="Your name (optional)" maxlength="40" autocomplete="off">
            <input class="notes-timecode" type="text" placeholder="Timecode (e.g. 1:23)" maxlength="20" autocomplete="off">
            <textarea class="notes-input" placeholder="Add a note…" rows="2" maxlength="500"></textarea>
            <button type="submit" class="notes-submit">ADD NOTE</button>
          </form>
        </div>
      </div>
    `;

    grid.appendChild(card);
  }

  body.appendChild(grid);
  section.appendChild(header);
  section.appendChild(body);

  header.addEventListener('click', () => toggleSection(section, header));

  section.addEventListener('click', e => {
    const copyBtn = e.target.closest('.copy-btn');
    if (copyBtn) { handleCopy(copyBtn, e); return; }

    const notesBtn = e.target.closest('.notes-btn');
    if (notesBtn && !e.target.closest('.notes-panel')) { toggleNotes(notesBtn); return; }

    const doneBtn = e.target.closest('.note-done-btn');
    if (doneBtn) { toggleNoteDone(doneBtn); return; }

    const deleteBtn = e.target.closest('.note-delete-btn');
    if (deleteBtn) { deleteNote(deleteBtn); return; }

    const resolvedToggle = e.target.closest('.resolved-toggle');
    if (resolvedToggle) { toggleResolved(resolvedToggle); return; }
  });

  section.addEventListener('submit', e => {
    const form = e.target.closest('.notes-form');
    if (form) { e.preventDefault(); addComment(form); }
  });

  section.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && e.target.closest('.notes-input')) {
      e.preventDefault();
      e.target.closest('.notes-form').requestSubmit();
    }
  });

  return section;
}

function toggleSection(section, header) {
  const isOpen = section.classList.contains('open');
  section.classList.toggle('open', !isOpen);
  header.setAttribute('aria-expanded', String(!isOpen));
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ─── Load & render ───────────────────────────────── */
let sparkSystem = null;

function setTotal(n) {
  const el = document.getElementById('total-copies');
  if (el) el.textContent = n;
}

async function loadVideos() {
  show('state-loading');
  hide('state-error');
  hide('content');

  try {
    const resp = await fetch('/api/videos');
    const json = await resp.json();
    if (!json.ok) throw new Error(json.error || 'Unknown error');

    const content = document.getElementById('content');
    content.innerHTML = '';

    if (!json.data || json.data.length === 0) {
      content.innerHTML = '<p style="text-align:center;color:var(--text-dim);font-family:var(--font-head);font-size:1.4rem;padding:60px 0">No videos found.</p>';
    } else {
      json.data.forEach((group, i) => {
        content.appendChild(renderYearSection(group, i === 0));
      });
    }

    setTotal(json.total ?? 0);
    hide('state-loading');
    show('content');
  } catch (err) {
    console.error(err);
    document.getElementById('error-text').textContent = 'Failed to load videos: ' + err.message;
    hide('state-loading');
    show('state-error');
  }
}

function show(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}

function hide(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}

/* ─── Re-sync ─────────────────────────────────────── */
async function syncVideos() {
  const btn = document.getElementById('sync-btn');
  btn.disabled = true;
  btn.classList.add('syncing');
  btn.querySelector('.sync-text').textContent = 'SYNCING…';

  try {
    const resp = await fetch('/api/sync', { method: 'POST' });
    const json = await resp.json();
    if (!json.ok) throw new Error(json.error || 'Sync failed');

    const content = document.getElementById('content');
    content.innerHTML = '';
    if (!json.data || json.data.length === 0) {
      content.innerHTML = '<p style="text-align:center;color:var(--text-dim);font-family:var(--font-head);font-size:1.4rem;padding:60px 0">No videos found.</p>';
    } else {
      json.data.forEach((group, i) => content.appendChild(renderYearSection(group, i === 0)));
    }

    setTotal(json.total ?? 0);
    btn.classList.remove('syncing');
    btn.classList.add('synced');
    btn.querySelector('.sync-text').textContent = 'SYNCED!';
    setTimeout(() => {
      btn.classList.remove('synced');
      btn.querySelector('.sync-text').textContent = 'RE-SYNC';
      btn.disabled = false;
    }, 2000);
  } catch (err) {
    btn.classList.remove('syncing');
    btn.querySelector('.sync-text').textContent = 'FAILED';
    setTimeout(() => {
      btn.querySelector('.sync-text').textContent = 'RE-SYNC';
      btn.disabled = false;
    }, 2000);
  }
}

/* ─── Init ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('bg-canvas');
  sparkSystem = new SparkSystem(canvas);
  loadVideos();
  document.getElementById('sync-btn').addEventListener('click', syncVideos);
});
