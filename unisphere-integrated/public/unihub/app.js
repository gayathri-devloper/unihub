let allProfiles = [];
let filteredProfiles = [];
let activeCategory = 'ALL';
let activeCluster = 'ALL';
let activeDesignation = 'ALL';

function getProfileCombinedClusters(p) {
  const rawList = [
    ...(p.clusters || []),
    ...(p.categories || []),
    ...(p.primary_category ? [p.primary_category] : [])
  ];
  const set = new Set();
  rawList.forEach(c => {
    if (c === 'Engineering' || c === 'Science Tech' || c === 'Science & Technology') {
      set.add('Engineering & Science Tech');
    } else if (c === 'Management' || c === 'Humanities') {
      set.add('Management & Humanities');
    } else if (c === 'Law') {
      set.add('Law');
    } else if (c === 'IKS') {
      set.add('IKS');
    } else if (c === 'Sustainability') {
      set.add('Sustainability');
    } else if (c === 'Health' || c === 'Public Health' || c === 'Health & Life Sciences' || c === 'Biosciences' || c === 'Bioscience' || c === 'Bio Science') {
      set.add('Health & Life Sciences');
    }
  });
  if (p.school === 'School of Biosciences') {
    set.add('Health & Life Sciences');
  }
  if (p.school === 'School of Engineering') {
    set.add('Engineering & Science Tech');
  }
  return Array.from(set);
}

let schoolChartInst = null;
let categoryChartInst = null;
let clusterChartInst = null;
let intlSchoolChartInst = null;
let qualChartInst = null;
let pubVolChartInst = null;
let projVolChartInst = null;
let desigChartInst = null;

document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  fetchData();
  setupEventListeners();
});

function initMobileMenu() {
  const btn = document.getElementById('mobileMenuBtn');
  const nav = document.querySelector('.main-nav');
  if (btn && nav) {
    btn.addEventListener('click', () => {
      nav.classList.toggle('mobile-active');
      const isOpen = nav.classList.contains('mobile-active');
      btn.innerHTML = isOpen
        ? '<i class="fa-solid fa-xmark"></i> Close'
        : '<i class="fa-solid fa-bars"></i> Menu';
    });
  }
}

async function fetchData() {
  try {
    // When UniHub is opened through UniSphere/Vite, /unihub/data.json is
    // proxied to the Flask backend. That keeps the UI backed by SQLite.
    // If the backend is temporarily unavailable, fall back to the bundled
    // snapshot so the portal never renders misleading zero-count KPIs.
    let resp = await fetch('data.json?v=' + Date.now(), { cache: 'no-store' });
    if (!resp.ok) {
      resp = await fetch('static_data.json?v=' + Date.now(), { cache: 'no-store' });
    }
    if (!resp.ok) throw new Error('UniHub data source not loaded');
    allProfiles = await resp.json();
    filteredProfiles = [...allProfiles];

    const urlParams = new URLSearchParams(window.location.search);
    const schParam = urlParams.get('school');
    const catParam = urlParams.get('category');

    // Restore saved filter state from sessionStorage if available
    let savedState = null;
    try {
      savedState = JSON.parse(sessionStorage.getItem('cu_filter_state') || 'null');
    } catch(e){}

    if (schParam) {
      document.getElementById('schoolFilter').value = schParam;
    } else if (savedState && savedState.school) {
      document.getElementById('schoolFilter').value = savedState.school;
    }

    if (catParam) {
      activeCategory = catParam;
    } else if (savedState && savedState.category) {
      activeCategory = savedState.category;
    }

    if (savedState) {
      if (savedState.query) document.getElementById('searchInput').value = savedState.query;
      if (savedState.type) document.getElementById('typeFilter').value = savedState.type;
      if (savedState.intlOnly !== undefined) document.getElementById('intlToggle').checked = savedState.intlOnly;
      if (savedState.cluster) activeCluster = savedState.cluster;
      if (savedState.designation) activeDesignation = savedState.designation;
    }

    // Sync Category Pills UI
    document.querySelectorAll('#categoryPills .pill-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.cat === activeCategory);
    });

    // Sync Cluster Pills UI
    document.querySelectorAll('#clusterPills .pill-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.cluster === activeCluster);
    });

    applyFilters();
    updateKPIs();
    renderCharts();
  } catch (err) {
    console.error('Error loading data:', err);
    document.getElementById('cardsGrid').innerHTML =
      '<div style="grid-column:1/-1;text-align:center;padding:3rem;color:#f88;">Failed to load directory data. Please refresh.</div>';
  }
}

function updateKPIs() {
  document.getElementById('kpiTotal').textContent = allProfiles.length;
  document.getElementById('kpiFaculty').textContent = allProfiles.filter(p => p.type === 'Faculty').length;
  document.getElementById('kpiResearchers').textContent = allProfiles.filter(p => p.type === 'Researcher').length;
  document.getElementById('kpiIntl').textContent = allProfiles.filter(p => p.has_international_exp).length;
}

function handleHoverPointer(e, elements) {
  e.native.target.style.cursor = elements.length ? 'pointer' : 'default';
}

function renderCharts() {
  // 1. School Bar Chart
  const schoolCounts = {};
  const schoolNames = {};
  allProfiles.forEach(p => {
    const s = p.school.replace('School of ', '');
    schoolCounts[s] = (schoolCounts[s] || 0) + 1;
    if (!schoolNames[s]) schoolNames[s] = [];
    if (schoolNames[s].length < 3) schoolNames[s].push(p.name);
  });

  const schoolCtx = document.getElementById('schoolChart').getContext('2d');
  if (schoolChartInst) schoolChartInst.destroy();
  schoolChartInst = new Chart(schoolCtx, {
    type: 'bar',
    data: {
      labels: Object.keys(schoolCounts),
      datasets: [{
        label: 'Faculty Count',
        data: Object.values(schoolCounts),
        backgroundColor: '#002561',
        hoverBackgroundColor: '#b8860b',
        borderRadius: 6
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        const label = Object.keys(schoolCounts)[elements[0].index];
        const fullSchool = allProfiles.find(p => p.school.includes(label))?.school;
        if (fullSchool) {
          document.getElementById('schoolFilter').value = fullSchool;
          applyFilters();
          document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              const label = ctx.label;
              const count = ctx.raw;
              const pct = ((count / allProfiles.length) * 100).toFixed(1);
              const names = (schoolNames[label] || []).join(', ');
              return [
                ' Total: ' + count + ' Profiles (' + pct + '%)',
                ' Key Faculty: ' + names + '...',
                ' 👉 Click bar to filter directory below'
              ];
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#64748b', font: { size: 10, weight: 'bold' } }, grid: { display: false } },
        y: { ticks: { color: '#64748b' }, grid: { color: '#e2e8f0' } }
      }
    }
  });

  // 2. Category Doughnut
  const cats = ['Law', 'Public Health', 'Sustainability', 'Science Tech', 'Humanities', 'IKS', 'Management'];
  const catCounts = {};
  const catNames = {};
  cats.forEach(c => { catCounts[c] = 0; catNames[c] = []; });
  allProfiles.forEach(p => {
    (p.categories || []).forEach(c => {
      if (catCounts[c] !== undefined) {
        catCounts[c]++;
        if (catNames[c].length < 3) catNames[c].push(p.name);
      }
    });
  });

  const catCtx = document.getElementById('categoryChart').getContext('2d');
  if (categoryChartInst) categoryChartInst.destroy();
  const isMobile = window.innerWidth < 768;
  categoryChartInst = new Chart(catCtx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(catCounts),
      datasets: [{
        data: Object.values(catCounts),
        backgroundColor: ['#002561','#b8860b','#10b981','#0284c7','#8b5cf6','#f59e0b','#ec4899'],
        hoverOffset: 14,
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        const catName = Object.keys(catCounts)[elements[0].index];
        activeCategory = catName;
        document.querySelectorAll('#categoryPills .pill-btn').forEach(b => {
          b.classList.toggle('active', b.dataset.cat === catName);
        });
        applyFilters();
        document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
      },
      plugins: {
        legend: {
          position: isMobile ? 'bottom' : 'right',
          labels: { color: '#334155', font: { size: isMobile ? 10 : 11, weight: '600' } }
        },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              const label = ctx.label || '';
              const names = (catNames[label] || []).join(', ');
              return [
                ' ' + label + ': ' + ctx.raw + ' Profiles',
                ' Key Scholars: ' + names + '...',
                ' 👉 Click slice to filter directory below'
              ];
            }
          }
        }
      }
    }
  });

  // 3. Cluster Polar Area - Combined Cluster Focus Breakdown
  const clusterOrder = [
    'Engineering & Science Tech',
    'Management & Humanities',
    'Health & Life Sciences',
    'Law',
    'IKS',
    'Sustainability'
  ];
  const clusterData = {};
  const clusterNames = {};
  clusterOrder.forEach(k => {
    clusterData[k] = 0;
    clusterNames[k] = [];
  });

  allProfiles.forEach(p => {
    const combined = getProfileCombinedClusters(p);
    combined.forEach(key => {
      if (clusterData[key] !== undefined) {
        clusterData[key]++;
        if (clusterNames[key].length < 3) clusterNames[key].push(p.name);
      }
    });
  });

  const clsCtx = document.getElementById('clusterChart').getContext('2d');
  if (clusterChartInst) clusterChartInst.destroy();
  clusterChartInst = new Chart(clsCtx, {
    type: 'polarArea',
    data: {
      labels: Object.keys(clusterData),
      datasets: [{
        data: Object.values(clusterData),
        backgroundColor: [
          'rgba(0, 37, 97, 0.75)',     // Deep Blue - Engineering & Science Tech
          'rgba(16, 185, 129, 0.75)',  // Emerald Green - Management & Humanities
          'rgba(236, 72, 153, 0.75)',  // Pink - Health & Life Sciences
          'rgba(184, 134, 11, 0.75)',  // Gold - Law
          'rgba(139, 92, 246, 0.75)',  // Purple - IKS
          'rgba(2, 132, 199, 0.75)'    // Sky Blue - Sustainability
        ],
        borderWidth: 1.5,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        const clsName = Object.keys(clusterData)[elements[0].index];
        activeCluster = clsName;
        document.querySelectorAll('#clusterPills .pill-btn').forEach(b => {
          b.classList.toggle('active', b.dataset.cluster === activeCluster);
        });
        applyFilters();
        document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
      },
      plugins: {
        legend: { position: 'bottom', labels: { color: '#334155', font: { weight: '600' } } },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              const names = (clusterNames[ctx.label] || []).join(', ');
              return [
                ' ' + ctx.label + ' Cluster: ' + ctx.raw + ' Profiles',
                ' Lead Faculty: ' + names + '...',
                ' 👉 Click slice to filter directory below'
              ];
            }
          }
        }
      },
      scales: { r: { ticks: { display: false }, grid: { color: '#cbd5e1' } } }
    }
  });

  // 4. International Exposure by School
  const intlCounts = {};
  allProfiles.filter(p => p.has_international_exp).forEach(p => {
    const s = p.school.replace('School of ', '');
    intlCounts[s] = (intlCounts[s] || 0) + 1;
  });

  const intlCtx = document.getElementById('intlSchoolChart').getContext('2d');
  if (intlSchoolChartInst) intlSchoolChartInst.destroy();
  intlSchoolChartInst = new Chart(intlCtx, {
    type: 'bar',
    data: {
      labels: Object.keys(intlCounts),
      datasets: [{
        label: 'Intl Profiles',
        data: Object.values(intlCounts),
        backgroundColor: '#10b981',
        hoverBackgroundColor: '#047857',
        borderRadius: 6
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        document.getElementById('intlToggle').checked = true;
        const label = Object.keys(intlCounts)[elements[0].index];
        const fullSchool = allProfiles.find(p => p.school.includes(label))?.school;
        if (fullSchool) document.getElementById('schoolFilter').value = fullSchool;
        applyFilters();
        document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              return [
                ' ' + ctx.label + ': ' + ctx.raw + ' International Track Profiles',
                ' 👉 Click bar to filter international view'
              ];
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#64748b', font: { size: 10, weight: 'bold' } }, grid: { display: false } },
        y: { ticks: { color: '#64748b' }, grid: { color: '#e2e8f0' } }
      }
    }
  });

  // 5. Academic Qualifications Breakdown (100% Accurate)
  const qualCounts = {
    'Ph.D. / Doctorate': allProfiles.filter(p => p.qual_level === 'Ph.D. / Doctorate').length,
    "Master's / Postgraduate": allProfiles.filter(p => p.qual_level === "Master's / Postgraduate").length,
    "Bachelor's / Professional": allProfiles.filter(p => p.qual_level === "Bachelor's / Professional").length
  };

  const qualCtx = document.getElementById('qualChart').getContext('2d');
  if (qualChartInst) qualChartInst.destroy();
  qualChartInst = new Chart(qualCtx, {
    type: 'pie',
    data: {
      labels: Object.keys(qualCounts),
      datasets: [{
        data: Object.values(qualCounts),
        backgroundColor: ['#002561', '#0284c7', '#b8860b'],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        const qLabel = Object.keys(qualCounts)[elements[0].index];
        filteredProfiles = allProfiles.filter(p => p.qual_level === qLabel);
        renderCards();
        document.getElementById('kpiTotal').textContent = filteredProfiles.length;
        document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
      },
      plugins: {
        legend: { position: 'bottom', labels: { color: '#334155', font: { size: 10, weight: '600' } } },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              const pct = ((ctx.raw / allProfiles.length) * 100).toFixed(1);
              return [
                ' ' + ctx.label + ': ' + ctx.raw + ' Faculty (' + pct + '%)',
                ' 👉 Click slice to filter directory'
              ];
            }
          }
        }
      }
    }
  });

  // 6. Publications Volume by School (NEW CHART 2)
  const pubVolCounts = {};
  allProfiles.forEach(p => {
    const s = p.school.replace('School of ', '');
    const count = (p.publications_list || []).length;
    pubVolCounts[s] = (pubVolCounts[s] || 0) + count;
  });

  const pubVolCtx = document.getElementById('pubVolChart').getContext('2d');
  if (pubVolChartInst) pubVolChartInst.destroy();
  pubVolChartInst = new Chart(pubVolCtx, {
    type: 'bar',
    data: {
      labels: Object.keys(pubVolCounts),
      datasets: [{
        label: 'Publications Volume',
        data: Object.values(pubVolCounts),
        backgroundColor: '#8b5cf6',
        hoverBackgroundColor: '#6d28d9',
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        const label = Object.keys(pubVolCounts)[elements[0].index];
        const fullSchool = allProfiles.find(p => p.school.includes(label))?.school;
        if (fullSchool) document.getElementById('schoolFilter').value = fullSchool;
        applyFilters();
        document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              return [
                ' ' + ctx.label + ': ' + ctx.raw + ' Recorded Publications',
                ' 👉 Click bar to view school faculty'
              ];
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: '#e2e8f0' } },
        y: { ticks: { color: '#64748b', font: { size: 9, weight: 'bold' } }, grid: { display: false } }
      }
    }
  });

  // 7. Projects Volume by School (NEW CHART)
  const projVolCounts = {};
  allProfiles.forEach(p => {
    const s = p.school.replace('School of ', '');
    const count = (p.projects_list || []).length;
    projVolCounts[s] = (projVolCounts[s] || 0) + count;
  });

  const projVolCtx = document.getElementById('projVolChart').getContext('2d');
  if (projVolChartInst) projVolChartInst.destroy();
  projVolChartInst = new Chart(projVolCtx, {
    type: 'bar',
    data: {
      labels: Object.keys(projVolCounts),
      datasets: [{
        label: 'Projects Volume',
        data: Object.values(projVolCounts),
        backgroundColor: '#10b981',
        hoverBackgroundColor: '#059669',
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        const label = Object.keys(projVolCounts)[elements[0].index];
        const fullSchool = allProfiles.find(p => p.school.includes(label))?.school;
        if (fullSchool) document.getElementById('schoolFilter').value = fullSchool;
        applyFilters();
        document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              return [
                ' ' + ctx.label + ': ' + ctx.raw + ' Recorded Projects',
                ' 👉 Click bar to view school faculty'
              ];
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: '#e2e8f0' } },
        y: { ticks: { color: '#64748b', font: { size: 9, weight: 'bold' } }, grid: { display: false } }
      }
    }
  });

  // 8. Faculty by Designation (100% Accurate Grouping)
  const desigCounts = {};
  allProfiles.forEach(p => {
    let d = p.designation_group || p.designation || p.type || 'Other';
    desigCounts[d] = (desigCounts[d] || 0) + 1;
  });

  const desigCtx = document.getElementById('desigChart').getContext('2d');
  if (desigChartInst) desigChartInst.destroy();
  desigChartInst = new Chart(desigCtx, {
    type: 'pie',
    data: {
      labels: Object.keys(desigCounts),
      datasets: [{
        data: Object.values(desigCounts),
        backgroundColor: ['#002561', '#b8860b', '#10b981', '#0284c7', '#8b5cf6', '#ec4899'],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: handleHoverPointer,
      onClick: (e, elements) => {
        if (!elements.length) return;
        const dLabel = Object.keys(desigCounts)[elements[0].index];
        activeDesignation = dLabel;
        applyFilters();
        document.getElementById('cardsGrid').scrollIntoView({ behavior: 'smooth' });
      },
      plugins: {
        legend: { position: 'bottom', labels: { color: '#334155', font: { size: 10, weight: '600' } } },
        tooltip: {
          padding: 12,
          callbacks: {
            label(ctx) {
              const pct = ((ctx.raw / allProfiles.length) * 100).toFixed(1);
              return [
                ' ' + ctx.label + ': ' + ctx.raw + ' Profiles (' + pct + '%)',
                ' 👉 Click slice to filter directory'
              ];
            }
          }
        }
      }
    }
  });
}

function setupEventListeners() {
  document.getElementById('searchInput').addEventListener('input', applyFilters);
  document.getElementById('typeFilter').addEventListener('change', applyFilters);
  document.getElementById('schoolFilter').addEventListener('change', applyFilters);
  document.getElementById('intlToggle').addEventListener('change', applyFilters);

  document.getElementById('resetFiltersBtn').addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('typeFilter').value = 'ALL';
    document.getElementById('schoolFilter').value = 'ALL';
    document.getElementById('intlToggle').checked = false;
    activeCategory = 'ALL';
    activeCluster = 'ALL';
    activeDesignation = 'ALL';
    document.querySelectorAll('#categoryPills .pill-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.cat === 'ALL');
    });
    document.querySelectorAll('#clusterPills .pill-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.cluster === 'ALL');
    });
    applyFilters();
  });

  document.querySelectorAll('#categoryPills .pill-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      document.querySelectorAll('#categoryPills .pill-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeCategory = e.target.dataset.cat;
      applyFilters();
    });
  });

  document.querySelectorAll('#clusterPills .pill-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      document.querySelectorAll('#clusterPills .pill-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeCluster = e.target.dataset.cluster;
      applyFilters();
    });
  });

}

function applyFilters() {
  const searchEl = document.getElementById('searchInput');
  const typeEl   = document.getElementById('typeFilter');
  const schoolEl = document.getElementById('schoolFilter');
  const intlEl   = document.getElementById('intlToggle');

  const query    = searchEl ? searchEl.value.toLowerCase().trim() : '';
  const selType  = typeEl ? typeEl.value : 'ALL';
  const selSchool= schoolEl ? schoolEl.value : 'ALL';
  const intlOnly = intlEl ? intlEl.checked : false;

  // Save active filter state to sessionStorage
  try {
    sessionStorage.setItem('cu_filter_state', JSON.stringify({
      query: searchEl ? searchEl.value : '',
      type: selType,
      school: selSchool,
      intlOnly: intlOnly,
      category: activeCategory,
      cluster: activeCluster,
      designation: activeDesignation
    }));
  } catch(e){}

  filteredProfiles = allProfiles.filter(p => {
    if (selType   !== 'ALL' && p.type   !== selType)   return false;
    if (selSchool !== 'ALL' && p.school !== selSchool) return false;
    if (activeCategory !== 'ALL' && !(p.categories || []).includes(activeCategory)) return false;
    if (activeCluster  !== 'ALL') {
      const pCombined = getProfileCombinedClusters(p);
      if (!pCombined.includes(activeCluster) && !(p.clusters || []).includes(activeCluster)) return false;
    }
    if (activeDesignation !== 'ALL' && (p.designation_group || p.designation || p.type || '') !== activeDesignation) return false;
    if (intlOnly && !p.has_international_exp) return false;
    if (query) {
      const hay = [p.name, p.designation, p.school, p.qualifications,
                   p.areas_of_expertise, p.bio, p.research_quest,
                   p.publications, p.projects, p.achievements].join(' ').toLowerCase();
      if (!hay.includes(query)) return false;
    }
    return true;
  });

  renderCards();
}

function renderCards() {
  const container = document.getElementById('cardsGrid');
  document.getElementById('resultsCount').textContent =
    'Showing ' + filteredProfiles.length + ' of ' + allProfiles.length + ' profiles';

  if (!filteredProfiles.length) {
    container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--text-muted);">No faculty or researchers matching your filters.</div>';
    return;
  }

  container.innerHTML = filteredProfiles.map(p => `
    <div class="faculty-card" onclick="window.location.href='profile.html?id=${p.id}'">
      ${p.has_international_exp ? '<span class="badge-intl"><i class="fa-solid fa-globe"></i> Intl Exp</span>' : ''}
      <div class="card-header-bar">
        <img src="${p.image_url}" alt="${p.name}" class="profile-avatar"
             onerror="this.src='https://chanakyauniversity.edu.in/wp-content/uploads/2026/02/default-img.jpg'">
        <div class="profile-basic">
          <h3>${p.name}</h3>
          <p class="designation">${p.designation || p.type}</p>
        </div>
      </div>
      <div class="card-body">
        <span class="school-tag">${p.school.replace('School of ', '')}</span>
        <div class="tag-cloud">
          ${Array.from(new Set(p.categories || [])).map(c => '<span class="badge-cat">' + c + '</span>').join('')}
        </div>
        <p class="bio-snippet">${p.bio || p.areas_of_expertise || p.qualifications || 'Chanakya University Academic Profile'}</p>
      </div>
      <div class="card-footer">
        <span style="color:var(--text-muted);font-size:0.75rem;font-weight:700;">${p.type}</span>
        <span class="view-profile-link">View Full Profile <i class="fa-solid fa-arrow-right"></i></span>
      </div>
    </div>
  `).join('');
}
