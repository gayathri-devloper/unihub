/* Upload menu (nav bar) + "Research paper" and "GitHub / project" forms.
 * Submissions are POSTed to the backend and stored permanently in the database. */
(function () {
  'use strict';

  const SCHOOLS = [
    'Arts, Humanities and Social Sciences', 'Management Sciences', 'Mathematics and Natural Sciences',
    'Law, Governance and Public Policy', 'Biosciences', 'Engineering'
  ];
  const DOMAINS = ['Law', 'Public Health', 'Sustainability', 'Science Tech', 'Humanities', 'IKS', 'Management'];
  const YEAR = new Date().getFullYear();

  const FORMS = {
    paper: {
      title: 'Research paper / publication',
      sub: 'Add publication details to the directory.',
      endpoint: '/api/submit/paper',
      submit: 'Add publication',
      success: 'Publication added to the directory.',
      page: 'publications.html',
      domains: ['General Research'].concat(DOMAINS),
      fields: [
        { name: 'title', label: 'Paper title', required: true },
        { name: 'author', label: 'Author / faculty name', required: true },
        { row: [{ name: 'school', label: 'School', type: 'school' }, { name: 'category', label: 'Domain', type: 'domain' }] },
        { name: 'year', label: 'Year', required: true, type: 'year' },
        { name: 'citation', label: 'Journal / publisher / citation' },
        { name: 'link', label: 'Paper link (DOI or URL)', required: true, placeholder: 'https://doi.org/...', type: 'url' },
        { name: 'about', label: 'About', required: true, type: 'textarea', placeholder: 'Describe the research or project.' }
      ]
    },
    repo: {
      title: 'GitHub / project',
      sub: 'Add a GitHub project to the repository dashboard.',
      endpoint: '/api/submit/project',
      submit: 'Add project',
      success: 'Project added to the repository dashboard.',
      page: 'projects.html',
      domains: DOMAINS,
      fields: [
        { name: 'title', label: 'Project title', required: true },
        { name: 'author', label: 'Principal investigator', required: true },
        { row: [{ name: 'school', label: 'School', type: 'school' }, { name: 'category', label: 'Domain', type: 'domain' }] },
        { name: 'year', label: 'Year', required: true, type: 'year' },
        { name: 'link', label: 'GitHub link', required: true, placeholder: 'https://github.com/user/repo', type: 'url' },
        { name: 'about', label: 'About', required: true, type: 'textarea', placeholder: 'Describe the research or project.' }
      ]
    }
  };

  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function fieldHTML(f, cfg, id) {
    const req = f.required ? ' <span class="up-req">*</span>' : '';
    let input;
    if (f.type === 'textarea') {
      input = `<textarea id="${id}" name="${f.name}" rows="5" maxlength="3000" placeholder="${esc(f.placeholder || '')}"></textarea>`;
    } else if (f.type === 'school') {
      input = `<select id="${id}" name="${f.name}">${SCHOOLS.map(s => `<option>${esc(s)}</option>`).join('')}</select>`;
    } else if (f.type === 'domain') {
      input = `<select id="${id}" name="${f.name}">${cfg.domains.map(s => `<option>${esc(s)}</option>`).join('')}</select>`;
    } else if (f.type === 'year') {
      input = `<input id="${id}" name="${f.name}" type="number" inputmode="numeric" min="1900" max="${YEAR + 1}" value="${YEAR}">`;
    } else {
      input = `<input id="${id}" name="${f.name}" type="text" maxlength="${f.type === 'url' ? 500 : 300}" placeholder="${esc(f.placeholder || '')}" autocomplete="off">`;
    }
    return `<div class="up-field"><label for="${id}">${esc(f.label)}${req}</label>${input}<div class="up-err" data-err="${f.name}"></div></div>`;
  }

  function buildModal(key, cfg) {
    const el = document.createElement('div');
    el.className = 'up-overlay';
    el.id = 'upModal-' + key;
    el.hidden = true;
    let n = 0;
    const body = cfg.fields.map(f => f.row
      ? `<div class="up-row">${f.row.map(x => fieldHTML(x, cfg, `up-${key}-${x.name}`)).join('')}</div>`
      : fieldHTML(f, cfg, `up-${key}-${f.name}`)).join('');
    el.innerHTML = `
      <div class="up-dialog" role="dialog" aria-modal="true" aria-labelledby="upTitle-${key}">
        <div class="up-head">
          <div><h2 id="upTitle-${key}">${esc(cfg.title)}</h2><p>${esc(cfg.sub)}</p></div>
          <button type="button" class="up-close" aria-label="Close"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <form class="up-form" novalidate>
          <div class="up-body">
            ${body}
            <input type="text" name="website" class="up-hp" tabindex="-1" autocomplete="off" aria-hidden="true">
            <div class="up-formerr" role="alert"></div>
          </div>
          <div class="up-foot">
            <button type="button" class="up-btn up-cancel">Cancel</button>
            <button type="submit" class="up-btn up-primary">${esc(cfg.submit)}</button>
          </div>
        </form>
      </div>`;
    document.body.appendChild(el);
    return el;
  }

  let lastFocus = null;
  const modals = {};

  function openModal(key) {
    closeMenu();
    const m = modals[key];
    lastFocus = document.activeElement;
    m.hidden = false;
    document.body.classList.add('up-lock');
    m.querySelector('.up-body').scrollTop = 0;
    setTimeout(() => m.querySelector('input,select,textarea').focus(), 30);
  }

  function closeModal(key) {
    const m = modals[key];
    if (!m || m.hidden) return;
    m.hidden = true;
    document.body.classList.remove('up-lock');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function toast(msg, ok) {
    const t = document.createElement('div');
    t.className = 'up-toast' + (ok === false ? ' up-toast-err' : '');
    t.setAttribute('role', 'status');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.classList.add('show'), 10);
    setTimeout(() => t.remove(), 4500);
  }

  function setErrors(m, fields, general) {
    m.querySelectorAll('.up-err').forEach(e => { e.textContent = ''; });
    m.querySelectorAll('.up-invalid').forEach(e => e.classList.remove('up-invalid'));
    Object.keys(fields || {}).forEach(k => {
      const e = m.querySelector(`[data-err="${k}"]`);
      if (e) { e.textContent = fields[k]; }
      const i = m.querySelector(`[name="${k}"]`);
      if (i) i.classList.add('up-invalid');
    });
    m.querySelector('.up-formerr').textContent = general || '';
  }

  function clientValidate(cfg, data) {
    const errs = {};
    cfg.fields.forEach(f => (f.row || [f]).forEach(x => {
      if (x.required && !String(data[x.name] || '').trim()) errs[x.name] = `${x.label} is required.`;
    }));
    if (data.link && !errs.link) {
      const v = data.link.trim();
      const isDoi = /^10\.\d{4,9}\/\S+$/.test(v);
      let okUrl = false;
      try { const u = new URL(v); okUrl = /^https?:$/.test(u.protocol); } catch (e) {}
      if (!okUrl && !(isDoi && cfg === FORMS.paper)) errs.link = 'Enter a valid link starting with https://';
    }
    const y = Number(data.year);
    if (!errs.year && !(Number.isInteger(y) && y >= 1900 && y <= YEAR + 1)) errs.year = 'Enter a valid 4-digit year.';
    return errs;
  }

  async function submit(key, ev) {
    ev.preventDefault();
    const cfg = FORMS[key], m = modals[key], form = m.querySelector('form');
    const data = Object.fromEntries(new FormData(form).entries());
    const errs = clientValidate(cfg, data);
    if (Object.keys(errs).length) {
      setErrors(m, errs, 'Please fix the highlighted fields.');
      const first = m.querySelector('.up-invalid'); if (first) first.focus();
      return;
    }
    setErrors(m, {}, '');
    const btn = form.querySelector('.up-primary');
    const label = btn.textContent;
    btn.disabled = true; btn.textContent = 'Saving…';
    try {
      const resp = await fetch(cfg.endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
      });
      const out = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setErrors(m, out.fields, out.error || 'Could not save. Please try again.');
        return;
      }
      form.reset();
      closeModal(key);
      toast(cfg.success + (out.linked_to ? ` Linked to ${out.linked_to.name}.` : ''));
      const here = location.pathname.split('/').pop() || 'index.html';
      setTimeout(() => { here === cfg.page ? location.reload() : (location.href = cfg.page); }, 900);
    } catch (e) {
      setErrors(m, {}, 'Cannot reach the server. Start the backend (run.bat / run.sh) and open http://localhost:5000.');
    } finally {
      btn.disabled = false; btn.textContent = label;
    }
  }

  // ---------- nav dropdown ----------
  let menu, menuBtn;
  function closeMenu() {
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    menuBtn.setAttribute('aria-expanded', 'false');
  }
  function toggleMenu() {
    if (!menu.hidden) return closeMenu();
    const r = menuBtn.getBoundingClientRect();
    menu.style.top = (r.bottom + 6) + 'px';
    menu.style.right = Math.max(8, window.innerWidth - r.right) + 'px';
    menu.hidden = false;
    menuBtn.setAttribute('aria-expanded', 'true');
    menu.querySelector('button').focus();
  }

  function init() {
    const navC = document.querySelector('.main-nav .nav-container');
    if (!navC || document.getElementById('navUploadBtn')) return;

    const wrap = document.createElement('div');
    wrap.className = 'nav-upload';
    wrap.innerHTML = `
      <button type="button" class="nav-upload-btn" id="navUploadBtn" aria-haspopup="menu" aria-expanded="false">
        <i class="fa-solid fa-arrow-up-from-bracket"></i><span>Upload</span><i class="fa-solid fa-chevron-down up-chev"></i>
      </button>
      <div class="nav-upload-menu" role="menu" hidden>
        <button type="button" role="menuitem" data-open="paper"><i class="fa-regular fa-file-lines"></i> Research Paper</button>
        <button type="button" role="menuitem" data-open="repo"><i class="fa-solid fa-code-branch"></i> Repository</button>
      </div>`;
    navC.appendChild(wrap);
    menuBtn = wrap.querySelector('.nav-upload-btn');
    menu = wrap.querySelector('.nav-upload-menu');
    menuBtn.addEventListener('click', e => { e.stopPropagation(); toggleMenu(); });
    menu.addEventListener('click', e => {
      const b = e.target.closest('[data-open]');
      if (b) openModal(b.dataset.open);
    });
    document.addEventListener('click', e => { if (!wrap.contains(e.target)) closeMenu(); });
    window.addEventListener('resize', closeMenu);
    window.addEventListener('scroll', closeMenu, { passive: true });

    Object.keys(FORMS).forEach(key => {
      const m = modals[key] = buildModal(key, FORMS[key]);
      m.addEventListener('mousedown', e => { if (e.target === m) closeModal(key); });
      m.querySelector('.up-close').addEventListener('click', () => closeModal(key));
      m.querySelector('.up-cancel').addEventListener('click', () => closeModal(key));
      m.querySelector('form').addEventListener('submit', ev => submit(key, ev));
    });

    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      closeMenu();
      Object.keys(modals).forEach(closeModal);
    });
  }

  // Opened by double-clicking the .html file? Uploads need the backend.
  if (location.protocol === 'file:') {
    document.addEventListener('DOMContentLoaded', () => {
      const bar = document.createElement('div');
      bar.style.cssText = 'background:#fef3c7;color:#78350f;padding:.6rem 1rem;font:600 .9rem Inter,sans-serif;text-align:center';
      bar.textContent = 'Backend not running: start it with run.bat / run.sh and open http://localhost:5000 instead of this file.';
      document.body.prepend(bar);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
