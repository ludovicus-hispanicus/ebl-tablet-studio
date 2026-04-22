// === State ===
let appMode = 'picker'; // 'picker' or 'renamer'
let customExportFolder = null; // null = use _Selected in root
let currentUserName = null; // collaboration: display name for assignments

const state = {
  rootFolder: null,
  subfolders: [],
  currentIndex: -1,
  images: [],
  selectedImage: null,       // primary selection (for assignment)
  selectedImages: new Set(),  // multi-selection (for rotation, etc.)
  lastClickedIndex: -1,       // for shift-click range selection
  assignments: {},            // imagePath -> viewCode (used by both modes)
  reverseAssignments: {},     // viewCode -> imagePath
  comboPending: null,
  comboTimer: null,
};

const VIEW_CODES = {
  '01': 'obverse', '02': 'reverse', '03': 'top',
  '04': 'bottom', '05': 'left', '06': 'right',
  'ot': 'obverse top', 'ob': 'obverse bottom',
  'ol': 'obverse left', 'or': 'obverse right',
  'rt': 'reverse top', 'rb': 'reverse bottom',
  'rl': 'reverse left', 'rr': 'reverse right',
};

const SHORTCUT_MAP = {
  '1': '01', '2': '02', '3': '03',
  '4': '04', '5': '05', '6': '06',
};

const COMBO_FIRST = new Set(['o', 'r']);
const COMBO_SECOND = new Set(['t', 'b', 'l', 'r']);

// === DOM References ===
const dom = {
  btnBrowse: document.getElementById('btn-browse'),
  folderPath: document.getElementById('folder-path'),
  btnPrev: document.getElementById('btn-prev'),
  btnNext: document.getElementById('btn-next'),
  btnSkip: document.getElementById('btn-skip'),
  subfolderInfo: document.getElementById('subfolder-info'),
  thumbGrid: document.getElementById('thumb-grid'),
  btnConfirm: document.getElementById('btn-confirm'),
  btnReset: document.getElementById('btn-reset'),
  statusText: document.getElementById('status-text'),
  statusCount: document.getElementById('status-count'),
  comboIndicator: document.getElementById('combo-indicator'),
  // Thumbnails panel modes
  thumbGridMode: document.getElementById('thumb-grid-mode'),
  viewerMode: document.getElementById('viewer-mode'),
  viewerStage: document.getElementById('viewer-stage'),
  viewerImage: document.getElementById('viewer-image'),
  viewerInfo: document.getElementById('viewer-info'),
};

// === Initialization ===
dom.btnBrowse.addEventListener('click', onBrowse);
dom.btnPrev.addEventListener('click', () => navigateSubfolder(-1));
dom.btnNext.addEventListener('click', () => navigateSubfolder(1));
dom.btnSkip.addEventListener('click', () => navigateSubfolder(1));
dom.btnConfirm.addEventListener('click', onConfirm);
dom.btnReset.addEventListener('click', onReset);

// Mode toggle
document.getElementById('btn-mode-renamer').addEventListener('click', () => switchMode('renamer'));
document.getElementById('btn-mode-picker').addEventListener('click', () => switchMode('picker'));
document.getElementById('btn-export-selected').addEventListener('click', onExportSelected);
document.getElementById('btn-convert-raw-selected').addEventListener('click', () => onConvertRawClick('selected'));
document.getElementById('btn-convert-raw-all').addEventListener('click', () => onConvertRawClick('all'));
document.getElementById('btn-convert-raw-project').addEventListener('click', () => onConvertRawClick('project'));

// Picker sub-tabs: Selected / Conversion / Settings
document.querySelectorAll('.picker-tab').forEach(btn => {
  btn.addEventListener('click', () => setPickerTab(btn.dataset.pickerTab));
});

document.getElementById('btn-picker-organize').addEventListener('click', onPickerOrganizeClick);
document.getElementById('btn-picker-group-selected').addEventListener('click', showGroupSelectedPrompt);
document.getElementById('btn-picker-group-confirm').addEventListener('click', confirmGroupSelected);
document.getElementById('btn-picker-group-cancel').addEventListener('click', hideGroupSelectedPrompt);
document.getElementById('picker-group-name-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); confirmGroupSelected(); }
  else if (e.key === 'Escape') { e.preventDefault(); hideGroupSelectedPrompt(); }
});
document.getElementById('btn-picker-clear-picks').addEventListener('click', onPickerClearPicks);
document.getElementById('btn-picker-reveal').addEventListener('click', onPickerRevealFolder);

document.getElementById('btn-tree-refresh').addEventListener('click', refreshFromDisk);
document.getElementById('btn-browse-export').addEventListener('click', async () => {
  const folder = await window.api.selectExportFolder();
  if (folder) {
    customExportFolder = folder;
    updateExportFolderDisplay();
  }
});
document.getElementById('btn-process').addEventListener('click', onProcessReady);

// Viewer mode controls
document.getElementById('viewer-back').addEventListener('click', exitViewerMode);
document.getElementById('viewer-prev').addEventListener('click', () => viewerNavigate(-1));
document.getElementById('viewer-next').addEventListener('click', () => viewerNavigate(1));
document.getElementById('viewer-reveal').addEventListener('click', () => {
  if (viewerCurrentPath) window.api.revealInExplorer(viewerCurrentPath);
});
document.getElementById('viewer-rot-ccw').addEventListener('click', () => viewerRotate(-90));
document.getElementById('viewer-rot-180').addEventListener('click', () => viewerRotate(180));
document.getElementById('viewer-rot-cw').addEventListener('click', () => viewerRotate(90));
document.getElementById('viewer-pick').addEventListener('click', () => {
  togglePick();
  updateViewerPickButton();
});
document.getElementById('viewer-delete').addEventListener('click', deleteCurrentImage);

// Rotation keyboard shortcuts still work (Shift+Left/Right/Down via onKeyDown).
// Sidebar rotation buttons were removed — floating per-thumbnail controls and
// the keyboard shortcuts cover the same workflow.

document.addEventListener('keydown', onKeyDown);

// Slot clicks
document.querySelectorAll('.slot[data-code]').forEach(slot => {
  slot.addEventListener('click', () => {
    assignCurrentImage(slot.dataset.code);
  });

  // Drop target
  slot.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    slot.classList.add('drag-over');
  });
  slot.addEventListener('dragleave', () => {
    slot.classList.remove('drag-over');
  });
  slot.addEventListener('drop', (e) => {
    e.preventDefault();
    slot.classList.remove('drag-over');
    const imagePath = e.dataTransfer.getData('text/plain');
    if (imagePath) {
      // Select the dropped image, then assign
      selectImage(imagePath);
      assignCurrentImage(slot.dataset.code);
    }
  });
});

// Help overlay
document.getElementById('btn-help').addEventListener('click', toggleHelp);

// Tree search: hide tree items whose name doesn't match the query (case-insensitive)
document.getElementById('tree-search').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  document.querySelectorAll('#tree-list .tree-item').forEach(item => {
    const name = item.textContent.toLowerCase();
    item.classList.toggle('hidden-by-search', q && !name.includes(q));
  });
});
document.getElementById('help-close').addEventListener('click', toggleHelp);
document.getElementById('help-overlay').addEventListener('click', (e) => {
  if (e.target.id === 'help-overlay') toggleHelp();
});

function toggleHelp() {
  document.getElementById('help-overlay').classList.toggle('hidden');
}

// === Resizable divider ===
const divider = document.getElementById('panel-divider');
const panelRight = document.getElementById('panel-right');
let isResizing = false;

divider.addEventListener('mousedown', (e) => {
  isResizing = true;
  divider.classList.add('dragging');
  document.body.style.cursor = 'col-resize';
  e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
  if (!isResizing) return;
  const newWidth = document.body.clientWidth - e.clientX;
  const clamped = Math.max(380, Math.min(newWidth, window.innerWidth * 0.7));
  panelRight.style.width = clamped + 'px';
});

document.addEventListener('mouseup', () => {
  if (isResizing) {
    isResizing = false;
    divider.classList.remove('dragging');
    document.body.style.cursor = '';
  }
});

// === Right Panel Tabs ===
// Tabs only change the right-panel content. The only tab that swaps the thumbnail
// grid is Results (to show stitched results). Leaving Results restores the
// image thumbnails for the currently selected tablet.
document.querySelectorAll('.result-view-tab').forEach(btn => {
  btn.addEventListener('click', () => setResultView(btn.dataset.resultView));
});

document.querySelectorAll('.right-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const newTab = tab.dataset.tab;
    const leavingResults = activeTab === 'results' && newTab !== 'results';

    document.querySelectorAll('.right-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`tab-${newTab}`).classList.add('active');

    activeTab = newTab;

    if (activeTab === 'results') {
      showResultThumbnails();
    } else {
      if (leavingResults) restoreThumbnailsForSelection();
      if (activeTab === 'tools') updateToolInfo();
    }
  });
});

// Re-render the thumbnail grid from the current state.images (the last-clicked
// tablet in the tree). Called when leaving the Results tab.
function restoreThumbnailsForSelection() {
  dom.thumbGrid.innerHTML = '';
  if (!state.images || state.images.length === 0) return;

  for (const img of state.images) {
    const card = createThumbCard(img);
    dom.thumbGrid.appendChild(card);
    loadThumbnail(img.path, card);
  }

  // Restore visual selection state
  if (state.selectedImage) {
    const card = getCardForImage(state.selectedImage);
    if (card) card.classList.add('primary');
  }
}

// Results tab controls
document.getElementById('btn-reprocess-all').addEventListener('click', reprocessAll);

// Auto-save notes ~500ms after the user stops typing.
let notesSaveTimer = null;
document.getElementById('result-notes').addEventListener('input', () => {
  clearTimeout(notesSaveTimer);
  notesSaveTimer = setTimeout(saveCurrentNotes, 500);
});

let dashboardNotesSaveTimer = null;
document.getElementById('dashboard-notes').addEventListener('input', () => {
  clearTimeout(dashboardNotesSaveTimer);
  dashboardNotesSaveTimer = setTimeout(saveDashboardNotes, 500);
});

// Settings dialog
document.getElementById('btn-settings').addEventListener('click', openSettings);

document.querySelectorAll('.settings-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const name = tab.dataset.settingsTab;
    document.querySelectorAll('.settings-tab').forEach(t => t.classList.toggle('active', t === tab));
    document.querySelectorAll('.settings-tab-panel').forEach(p => {
      p.classList.toggle('active', p.id === `settings-tab-${name}`);
    });
  });
});

// Background swatch picker — clicking a swatch updates the hidden input
// and toggles the selected state. saveSettings reads #setting-background
// unchanged, so no save-side change needed.
document.querySelectorAll('.bg-swatch-setting').forEach(btn => {
  btn.addEventListener('click', () => {
    const value = btn.dataset.bg;
    document.getElementById('setting-background').value = value;
    document.querySelectorAll('.bg-swatch-setting').forEach(b =>
      b.classList.toggle('selected', b === btn));
  });
});
document.getElementById('settings-close').addEventListener('click', closeSettings);
document.getElementById('settings-save').addEventListener('click', saveSettings);
document.getElementById('setting-new-project').addEventListener('click', showNewProjectPrompt);
document.getElementById('setting-new-project-cancel').addEventListener('click', hideNewProjectPrompt);
document.getElementById('setting-new-project-confirm').addEventListener('click', createNewProject);
document.getElementById('setting-new-project-name').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); createNewProject(); }
  else if (e.key === 'Escape') { e.preventDefault(); hideNewProjectPrompt(); }
});
document.getElementById('setting-delete-project').addEventListener('click', deleteSelectedProject);
document.getElementById('setting-browse-measurements').addEventListener('click', async () => {
  const path = await window.api.selectMeasurementsFile();
  if (path) document.getElementById('setting-measurements').value = path;
});
document.getElementById('setting-clear-measurements').addEventListener('click', () => {
  document.getElementById('setting-measurements').value = '';
});
document.getElementById('setting-browse-logo').addEventListener('click', async () => {
  const path = await window.api.selectLogoFile();
  if (path) document.getElementById('setting-logo-path').value = path;
});
document.getElementById('setting-clear-logo').addEventListener('click', () => {
  document.getElementById('setting-logo-path').value = '';
});
document.getElementById('setting-browse-ruler').addEventListener('click', async () => {
  const p = await window.api.selectRulerFile();
  if (p) {
    document.getElementById('setting-ruler-file').value = `file:${p}`;
    await populateRulerGrid();
  }
});
document.getElementById('setting-clear-ruler').addEventListener('click', async () => {
  document.getElementById('setting-ruler-file').value = '';
  await populateRulerGrid();
});
document.getElementById('setting-open-ruler').addEventListener('click', async () => {
  document.getElementById('ruler-overlay').classList.remove('hidden');
  await populateRulerGrid();
});
document.getElementById('ruler-close').addEventListener('click', closeRulerOverlay);
document.getElementById('ruler-done').addEventListener('click', closeRulerOverlay);
document.getElementById('ruler-overlay').addEventListener('click', (e) => {
  if (e.target.id === 'ruler-overlay') closeRulerOverlay();
});
function closeRulerOverlay() {
  document.getElementById('ruler-overlay').classList.add('hidden');
}

// Builds the ruler grid grouped by the new scheme:
//
//   General           — general-purpose rulers (freely usable)
//     • General External photo ruler
//     • BM scale bars (donated by the British Museum for free use)
//   British Museum    — reserved for future BM-specific rulers
//   Iraq Museum       — IM photo ruler
//   Projects          — eBL, Sippar Library, Jena (black background)
//
// Scale-bar sets (BM, Black/Jena) present BOTH:
//   • a "Use whole set (auto-sized)" card that selects the set and lets
//     the stitcher auto-pick 1/2/5 cm based on tablet width
//   • individual 1/2/5 cm cards that force a specific size
//
// Selection is stored in the hidden #setting-ruler-file input as either
// `file:<abs-path>` or `set:<group-id>`. saveSettings parses it into
// project.ruler_file / project.ruler_set.
async function populateRulerGrid() {
  const grid = document.getElementById('ruler-grid');
  const input = document.getElementById('setting-ruler-file');
  grid.innerHTML = '<div class="ruler-loading">Loading\u2026</div>';

  const { builtin = [] } = await window.api.listRulers();
  const selected = (input.value || '').trim();

  // Partition by group
  const byGroup = { general: [], bm_donated: [], black_jena: [],
                    iraq_museum: [], project_ebl: [], project_sippar: [] };
  for (const r of builtin) {
    if (byGroup[r.group]) byGroup[r.group].push({ ...r, kind: 'builtin' });
    else byGroup.general.push({ ...r, kind: 'builtin' });
  }

  // Treat a legacy raw-path value (no "file:" / "set:" prefix) as a file path
  const legacyFile = (!selected.includes(':') && selected) ? selected : null;
  let selectedFile = selected.startsWith('file:') ? selected.slice(5) : legacyFile;
  const selectedSet = selected.startsWith('set:') ? selected.slice(4) : null;

  // The built-in stitcher project JSONs store bare filenames (e.g.
  // "General_External_photo_ruler.svg") rather than absolute paths.
  // If the saved value is a bare name, match it against the built-ins by
  // basename and promote it to the full path so it matches a built-in card
  // (and `fs.existsSync` works for the preview).
  const basenameOf = (p) => (p || '').replace(/\\/g, '/').split('/').pop();
  if (selectedFile && !selectedFile.includes('/') && !selectedFile.includes('\\')) {
    const match = builtin.find(r => basenameOf(r.path) === selectedFile);
    if (match) selectedFile = match.path;
  }

  // Append custom uploaded ruler (not matching any built-in) under General
  const isBuiltinSelected = selectedFile && builtin.some(r => r.path === selectedFile);
  if (selectedFile && !isBuiltinSelected) {
    const name = basenameOf(selectedFile) || selectedFile;
    byGroup.general.push({ id: 'custom', label: name, path: selectedFile, preview: selectedFile, kind: 'custom' });
  }

  // Visual-group layout:
  //   General         — External photo ruler + Black-background scale bars
  //                     (formerly "Jena"; now treated as general-purpose)
  //   British Museum  — BM_*_scale bars (they belong to the BM)
  //   Iraq Museum     — IM photo ruler
  //   Projects        — eBL, Sippar Library
  const sections = [
    {
      title: 'General', note: null,
      items: byGroup.general,
      setsBefore: [], setsAfter: byGroup.black_jena.length ? [
        { setId: 'black_jena', label: 'Black background scale bars (auto-sized)',
          sample: byGroup.black_jena.find(r => r.sortKey === 5) || byGroup.black_jena[0],
          badge: null },
      ] : [],
      extras: byGroup.black_jena,
      extrasNote: byGroup.black_jena.length
        ? 'Black-background scale bars — size (1 / 2 / 5 cm) is auto-selected based on tablet width. Pick one below only to force a specific size.'
        : null,
    },
    {
      title: 'British Museum',
      note: 'Scale bars donated by the British Museum to be used freely.',
      items: [],
      setsBefore: [], setsAfter: byGroup.bm_donated.length ? [
        { setId: 'bm_donated', label: 'BM scale bars (auto-sized)',
          sample: byGroup.bm_donated.find(r => r.sortKey === 5) || byGroup.bm_donated[0],
          badge: null },
      ] : [],
      extras: byGroup.bm_donated,
      extrasNote: byGroup.bm_donated.length
        ? 'Size (1 / 2 / 5 cm) is auto-selected based on tablet width. Pick one below only to force a specific size.'
        : null,
    },
    {
      title: 'Iraq Museum', note: null,
      items: byGroup.iraq_museum, setsBefore: [], setsAfter: [],
      extras: [], extrasNote: null,
    },
    {
      title: 'Projects', note: null,
      items: [...byGroup.project_ebl, ...byGroup.project_sippar],
      setsBefore: [], setsAfter: [],
      extras: [], extrasNote: null,
    },
  ];

  const total = builtin.length + (selectedFile && !isBuiltinSelected ? 1 : 0);
  if (total === 0) {
    grid.innerHTML = '<div class="ruler-loading">No rulers found. Upload a custom one below.</div>';
    return;
  }

  grid.innerHTML = '';

  const makeCard = (r, opts = {}) => {
    const card = document.createElement('div');
    const isSelected = opts.setId
      ? (selectedSet === opts.setId)
      : (r.path === selectedFile);
    card.className = 'ruler-card' + (isSelected ? ' selected' : '');
    card.dataset.selection = opts.setId ? `set:${opts.setId}` : `file:${r.path}`;
    card.title = opts.setId ? opts.setId : r.path;

    const img = document.createElement('img');
    img.alt = r.label;
    card.appendChild(img);

    const name = document.createElement('div');
    name.className = 'ruler-card-name';
    name.textContent = opts.setLabel || r.label;
    card.appendChild(name);

    if (r.kind === 'custom') {
      const badge = document.createElement('div');
      badge.className = 'ruler-card-badge';
      badge.textContent = 'Custom';
      card.appendChild(badge);
    } else if (opts.badge) {
      const badge = document.createElement('div');
      badge.className = 'ruler-card-badge';
      badge.textContent = opts.badge;
      card.appendChild(badge);
    } else if (opts.setId) {
      const badge = document.createElement('div');
      badge.className = 'ruler-card-badge';
      badge.textContent = 'Auto-sized';
      card.appendChild(badge);
    }

    card.addEventListener('click', () => {
      input.value = card.dataset.selection;
      grid.querySelectorAll('.ruler-card').forEach(c => c.classList.toggle('selected', c === card));
    });

    (async () => {
      const src = r.preview || r.path;
      const dataUrl = await window.api.getRulerPreview(src);
      if (dataUrl) {
        img.src = dataUrl;
      } else {
        console.warn('[ruler preview] null for', src, 'label=', r.label);
      }
      img.onerror = () => console.warn('[ruler preview] <img> failed for', r.label, 'src starts with', (img.src || '').slice(0, 80));
    })();

    return card;
  };

  for (const section of sections) {
    const hasContent = section.items.length > 0 ||
                       section.setsBefore.length > 0 ||
                       section.setsAfter.length > 0 ||
                       section.extras.length > 0 ||
                       !!section.note;
    if (!hasContent) continue;

    const sec = document.createElement('div');
    sec.className = 'ruler-group';

    const header = document.createElement('div');
    header.className = 'ruler-group-title';
    header.textContent = section.title;
    sec.appendChild(header);

    if (section.note) {
      const noteEl = document.createElement('div');
      noteEl.className = 'ruler-group-note';
      noteEl.textContent = section.note;
      sec.appendChild(noteEl);
    }

    // Primary grid: individual items + "whole set" cards
    const inner = document.createElement('div');
    inner.className = 'ruler-group-grid';
    for (const s of section.setsBefore) {
      if (!s.sample) continue;
      inner.appendChild(makeCard(s.sample, { setId: s.setId, setLabel: s.label, badge: s.badge }));
    }
    for (const r of section.items) inner.appendChild(makeCard(r));
    for (const s of section.setsAfter) {
      if (!s.sample) continue;
      inner.appendChild(makeCard(s.sample, { setId: s.setId, setLabel: s.label, badge: s.badge }));
    }
    if (inner.children.length > 0) sec.appendChild(inner);

    // Secondary: size-override cards for the scale-bar set (same group)
    if (section.extras && section.extras.length > 0) {
      if (section.extrasNote) {
        const noteEl = document.createElement('div');
        noteEl.className = 'ruler-group-note';
        noteEl.textContent = section.extrasNote;
        sec.appendChild(noteEl);
      }
      const extrasGrid = document.createElement('div');
      extrasGrid.className = 'ruler-group-grid ruler-group-grid-extras';
      for (const r of section.extras) extrasGrid.appendChild(makeCard(r));
      sec.appendChild(extrasGrid);
    }

    grid.appendChild(sec);
  }
}
document.getElementById('settings-overlay').addEventListener('click', (e) => {
  if (e.target.id === 'settings-overlay') closeSettings();
});

// Stitcher progress
window.api.onStitcherProgress((event) => {
  handleStitcherProgress(event);
});
document.getElementById('result-preview-close').addEventListener('click', closeResultPreview);
document.getElementById('result-preview-prev').addEventListener('click', () => navigateResultPreview(-1));
document.getElementById('result-preview-next').addEventListener('click', () => navigateResultPreview(1));
document.getElementById('result-toggle-revision').addEventListener('click', () => setResultStatus('revision'));
document.getElementById('result-toggle-updated').addEventListener('click', () => setResultStatus('updated'));
document.getElementById('result-toggle-sent').addEventListener('click', () => setResultStatus('sent'));
document.getElementById('result-preview-reveal').addEventListener('click', () => {
  if (resultsState.results[resultsState.currentIndex]) {
    window.api.revealInExplorer(resultsState.results[resultsState.currentIndex].jpgPath);
  }
});
document.getElementById('result-preview-edit').addEventListener('click', editSelectedForCurrentResult);
document.getElementById('result-preview-overlay').addEventListener('click', (e) => {
  // Don't close if the "click" was actually the end of a pan drag
  if (resultZoom.moved) { resultZoom.moved = false; return; }
  if (e.target.id === 'result-preview-overlay') closeResultPreview();
});

// Zoom + pan on the result preview overlay
document.getElementById('result-preview-overlay').addEventListener('wheel', onResultWheel, { passive: false });
document.getElementById('result-preview-overlay').addEventListener('mousedown', onResultPanStart);
window.addEventListener('mousemove', onResultPanMove);
window.addEventListener('mouseup', onResultPanEnd);

// Ctrl+A to select all
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'a') {
    e.preventDefault();
    selectAll();
  }
});

// === Browse ===
async function onBrowse() {
  const folder = await window.api.selectFolder();
  if (!folder) return;
  await openFolder(folder);
}

async function openFolder(folder) {
  state.rootFolder = folder;
  dom.folderPath.textContent = folder;
  localStorage.setItem('lastFolder', folder);
  setStatus('Scanning folder...');

  const result = await window.api.scanFolder(folder);
  state.subfolders = result.subfolders;
  state.looseImages = result.looseImages || [];

  if (state.subfolders.length === 0 && state.looseImages.length === 0) {
    setStatus('No images found in this folder.');
    return;
  }
  if (state.subfolders.length === 0 && state.looseImages.length > 0) {
    setStatus(`This folder has ${state.looseImages.length} image(s) not grouped into subfolders — see "(Loose files)" in the tree.`);
  }

  setStatus(`Found ${state.subfolders.length} subfolder(s) with ${result.totalImages} images. Click a folder to start.`);
  state.currentIndex = -1;  // no folder auto-opened; user picks one from the tree

  // Load statuses early so tree icons show immediately
  resultsState.reviewStatus = await window.api.loadReviewStatus(getResultsRoot());

  buildTreeView();
  loadResults();
  // Thumbnail grid stays empty until the user clicks a folder in the tree.
  dom.thumbGrid.innerHTML = '';
  dom.subfolderInfo.textContent = '';
  updateTreeStatusIcons();
  // Start live collaboration refresh if in renamer mode
  if (appMode === 'renamer') startStatusRefresh();
}

// Restore last folder on startup
(async () => {
  const lastFolder = localStorage.getItem('lastFolder');
  if (lastFolder) {
    openFolder(lastFolder);
  }
})();

// === Tree View ===
function buildTreeView() {
  if (appMode === 'renamer') {
    buildSelectedTree();
    return;
  }
  buildSourceTree();
}

async function buildSourceTree() {
  const treeList = document.getElementById('tree-list');
  treeList.innerHTML = '';
  document.getElementById('tree-header').textContent = 'Folders';

  // Pseudo-entry for images at the root with no subfolder. Lets the user
  // browse / select / group them without flipping a modal on folder open.
  if ((state.looseImages || []).length > 0) {
    const item = document.createElement('div');
    item.className = 'tree-item tree-loose-entry';
    item.dataset.index = '-1';
    item.innerHTML = `<span class="tree-name">(Loose files)</span><span class="tree-count">(${state.looseImages.length})</span>`;
    item.title = 'Image files at the root of this folder, not grouped into tablet subfolders. Click to browse and group them.';
    item.addEventListener('click', () => {
      loadLoosePickerImages();
    });
    treeList.appendChild(item);
  }

  // Cross-reference against the export folder so picker rows can show
  // "picked / total" and a ✓ when the tablet has been exported. The scan is
  // cheap (readdir + image-extension filter per subfolder) and runs once per
  // tree build; we silently fall back to no-export-info on error.
  //
  // The renamer's export step normalizes "Si 41" → "Si.41" on disk (see
  // stitcher/lib/workflow_cleanup.py:normalize_subfolder_names), so we apply
  // the same normalization to both sides before matching.
  const normalizeTabletId = (name) => (name || '').replace(/(\w+)\s+(\d+)/g, '$1.$2');
  const exportBase = customExportFolder || (state.rootFolder ? state.rootFolder + '/_Selected' : null);
  const exportedCounts = new Map();
  if (exportBase) {
    try {
      const exported = await window.api.scanSelectedFolder(exportBase);
      for (const f of exported) exportedCounts.set(normalizeTabletId(f.name), f.imageCount || 0);
    } catch { /* ignore — exportBase may not exist yet */ }
  }

  state.subfolders.forEach((sub, idx) => {
    const item = document.createElement('div');
    item.className = 'tree-item';
    item.dataset.index = idx;
    const expCount = exportedCounts.get(normalizeTabletId(sub.name)) || 0;
    const countText = expCount > 0
      ? `(${expCount}/${sub.imageCount})`
      : `(${sub.imageCount})`;
    const check = expCount > 0 ? '<span class="tree-exported-check" title="Exported">\u2713</span>' : '';
    item.innerHTML = `<span class="tree-name">${sub.name}</span><span class="tree-count">${countText}</span>${check}`;
    item.addEventListener('click', () => {
      state.currentIndex = idx;
      loadCurrentSubfolder();
    });
    treeList.appendChild(item);
  });
}

function updateTreeActive() {
  if (appMode === 'renamer') return; // don't highlight in selected tree
  document.querySelectorAll('.tree-item').forEach(item => {
    item.classList.toggle('active', parseInt(item.dataset.index) === state.currentIndex);
  });
  // Scroll active into view
  const active = document.querySelector('.tree-item.active');
  if (active) active.scrollIntoView({ block: 'nearest' });
}

// === Subfolder Navigation ===
function navigateSubfolder(direction) {
  if (appMode === 'renamer' && selectedTreeFolders.length > 0) {
    const newIndex = selectedTreeIndex + direction;
    if (newIndex < 0 || newIndex >= selectedTreeFolders.length) return;
    loadSelectedFolder(newIndex);
    return;
  }
  const newIndex = state.currentIndex + direction;
  if (newIndex < 0 || newIndex >= state.subfolders.length) return;
  state.currentIndex = newIndex;
  loadCurrentSubfolder();
}

async function loadCurrentSubfolder() {
  const sub = state.subfolders[state.currentIndex];
  if (!sub) return;
  // Exit the single-image viewer when switching folders — otherwise the
  // viewer stays open pointing at a stale image from the previous folder.
  if (isViewerOpen()) exitViewerMode();
  const total = state.subfolders.length;

  dom.subfolderInfo.textContent = `${sub.name}  (${state.currentIndex + 1} / ${total})`;
  dom.btnPrev.disabled = state.currentIndex === 0;
  dom.btnNext.disabled = state.currentIndex >= total - 1;
  dom.btnSkip.disabled = state.currentIndex >= total - 1;
  updateTreeActive();

  // Reset state
  state.images = sub.images;
  state.selectedImage = null;
  state.selectedImages.clear();
  state.lastClickedIndex = -1;
  state.assignments = {};
  state.reverseAssignments = {};

  // Auto-detect existing assignments
  for (const img of state.images) {
    if (img.detectedView && !state.reverseAssignments[img.detectedView]) {
      state.assignments[img.path] = img.detectedView;
      state.reverseAssignments[img.detectedView] = img.path;
    }
  }

  // Render thumbnails
  dom.thumbGrid.innerHTML = '';
  setStatus(`Loading ${state.images.length} thumbnails...`);

  for (const img of state.images) {
    const card = createThumbCard(img);
    dom.thumbGrid.appendChild(card);
    loadThumbnail(img.path, card);
  }

  // Select first image
  if (state.images.length > 0) {
    selectImage(state.images[0].path);
  }

  // In picker mode, load saved picks from picks.json
  if (appMode === 'picker') {
    const savedPicks = await window.api.loadPicks(sub.path);
    // savedPicks maps filename -> viewCode. Translate to full paths.
    if (savedPicks && Object.keys(savedPicks).length > 0) {
      for (const [filename, viewCode] of Object.entries(savedPicks)) {
        const img = state.images.find(i => i.name === filename);
        if (img && (viewCode === 'pick' || !state.reverseAssignments[viewCode])) {
          state.assignments[img.path] = viewCode;
          if (viewCode !== 'pick') state.reverseAssignments[viewCode] = img.path;
        }
      }
      // Update card badges for all loaded picks
      for (const imgPath of Object.keys(state.assignments)) {
        updateCardBadge(imgPath);
      }
    }
  }

  updateStructureDiagram();
  updatePickerList();
  updateButtons();
  updateStatusCount();
  updateResultsTab();
}

function createThumbCard(img) {
  const card = document.createElement('div');
  card.className = 'thumb-card';
  card.dataset.path = img.path;

  if (state.assignments[img.path]) {
    card.classList.add('assigned');
  }

  // Assignment badge (top-right)
  const badge = document.createElement('div');
  badge.className = 'thumb-badge';
  const code = state.assignments[img.path];
  badge.textContent = code ? `_${code}` : '';
  card.appendChild(badge);

  // Image
  const imgEl = document.createElement('img');
  imgEl.alt = img.name;
  imgEl.src = '';
  card.appendChild(imgEl);

  // Floating rotation buttons (appear on hover/selection)
  const rotBar = document.createElement('div');
  rotBar.className = 'thumb-rotate-bar';
  rotBar.innerHTML = `
    <button class="rot-btn" data-deg="-90" title="Rotate 90° CCW">&#x21B6;</button>
    <button class="rot-btn" data-deg="180" title="Rotate 180°">&#x21BB;</button>
    <button class="rot-btn" data-deg="90" title="Rotate 90° CW">&#x21B7;</button>
  `;
  card.appendChild(rotBar);

  // Rotation button clicks — rotate THIS card's image, not the global selection
  rotBar.querySelectorAll('.rot-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const degrees = parseInt(btn.dataset.deg);
      rotateSingleImage(img.path, degrees, card);
    });
  });

  // Filename
  const name = document.createElement('div');
  name.className = 'thumb-name';
  name.textContent = img.name;
  card.appendChild(name);

  // Drag support
  card.setAttribute('draggable', 'true');
  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', img.path);
    e.dataTransfer.effectAllowed = 'move';
    card.classList.add('dragging');
  });
  card.addEventListener('dragend', () => {
    card.classList.remove('dragging');
  });

  // Right-click: reveal in explorer
  card.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    window.api.revealInExplorer(img.path);
  });

  // Click handlers with modifier support
  card.addEventListener('click', (e) => {
    if (e.target.closest('.rot-btn')) return;
    handleThumbClick(img.path, e);
  });
  card.addEventListener('dblclick', (e) => {
    if (e.target.closest('.rot-btn')) return;
    enterViewerMode(img.path);
  });

  return card;
}

async function loadThumbnail(imagePath, card) {
  const dataUrl = await window.api.getThumbnail(imagePath);
  if (dataUrl) {
    const imgEl = card.querySelector('img');
    imgEl.src = dataUrl;
  }
}

// === Selection ===

function handleThumbClick(imagePath, event) {
  const clickedIndex = state.images.findIndex(i => i.path === imagePath);

  if (event.shiftKey && state.lastClickedIndex >= 0) {
    // Shift+click: range selection
    const start = Math.min(state.lastClickedIndex, clickedIndex);
    const end = Math.max(state.lastClickedIndex, clickedIndex);
    state.selectedImages.clear();
    for (let i = start; i <= end; i++) {
      state.selectedImages.add(state.images[i].path);
    }
    state.selectedImage = imagePath;
  } else if (event.ctrlKey || event.metaKey) {
    // Ctrl+click: toggle individual
    if (state.selectedImages.has(imagePath)) {
      state.selectedImages.delete(imagePath);
      // If we deselected the primary, pick another
      if (state.selectedImage === imagePath) {
        state.selectedImage = state.selectedImages.size > 0
          ? state.selectedImages.values().next().value
          : null;
      }
    } else {
      state.selectedImages.add(imagePath);
      state.selectedImage = imagePath;
    }
    state.lastClickedIndex = clickedIndex;
  } else {
    // Normal click: single selection
    state.selectedImages.clear();
    state.selectedImages.add(imagePath);
    state.selectedImage = imagePath;
    state.lastClickedIndex = clickedIndex;
  }

  updateSelectionUI();
  updateStatusCount();
}

function selectImage(imagePath) {
  // Single selection (used by keyboard nav, auto-advance)
  state.selectedImages.clear();
  state.selectedImages.add(imagePath);
  state.selectedImage = imagePath;
  state.lastClickedIndex = state.images.findIndex(i => i.path === imagePath);

  updateSelectionUI();
  updateStatusCount();
}

function selectAll() {
  state.selectedImages.clear();
  for (const img of state.images) {
    state.selectedImages.add(img.path);
  }
  if (state.images.length > 0 && !state.selectedImage) {
    state.selectedImage = state.images[0].path;
  }
  updateSelectionUI();
  updateStatusCount();
}

function selectAdjacent(direction) {
  if (!state.images.length) return;

  let idx = state.images.findIndex(img => img.path === state.selectedImage);
  if (idx === -1) idx = 0;

  const newIdx = idx + direction;
  if (newIdx >= 0 && newIdx < state.images.length) {
    selectImage(state.images[newIdx].path);
  }
}

function updateSelectionUI() {
  // Update all cards
  document.querySelectorAll('.thumb-card').forEach(card => {
    const path = card.dataset.path;
    const isSelected = state.selectedImages.has(path);
    const isPrimary = path === state.selectedImage;

    card.classList.toggle('selected', isSelected);
    card.classList.toggle('primary', isPrimary);
  });

  // Refresh the Picker's Convert-RAW button counts whenever the selection
  // changes — selection state is the only input the "Convert selected (N)"
  // label depends on that isn't already tracked elsewhere.
  if (typeof updateConvertRawButtons === 'function') {
    updateConvertRawButtons();
  }

  // Scroll primary into view
  if (state.selectedImage) {
    const card = getCardForImage(state.selectedImage);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // If the viewer is open, swap its image to match the newly selected one
  if (isViewerOpen() && state.selectedImage && state.selectedImage !== viewerCurrentPath) {
    loadViewerImage(state.selectedImage);
  }

  // Keep the Tools tab Info section fresh
  if (activeTab === 'tools') updateToolInfo();
}

// === Assignment ===
function assignCurrentImage(viewCode) {
  if (!state.selectedImage || !VIEW_CODES[viewCode]) return;

  const oldCode = state.assignments[state.selectedImage];
  if (oldCode) {
    delete state.reverseAssignments[oldCode];
  }

  const oldImage = state.reverseAssignments[viewCode];
  if (oldImage) {
    delete state.assignments[oldImage];
    updateCardBadge(oldImage);
  }

  state.assignments[state.selectedImage] = viewCode;
  state.reverseAssignments[viewCode] = state.selectedImage;

  updateCardBadge(state.selectedImage);
  updateStructureDiagram();
  updatePickerList();
  updateButtons();
  updateStatusCount();
  if (appMode === 'picker') savePicksDebounced();

  autoAdvanceSelection();
}

function unassignCurrentImage() {
  if (!state.selectedImage) return;

  const code = state.assignments[state.selectedImage];
  if (!code) return;

  delete state.reverseAssignments[code];
  delete state.assignments[state.selectedImage];

  updateCardBadge(state.selectedImage);
  updateStructureDiagram();
  updatePickerList();
  updateButtons();
  updateStatusCount();
  if (appMode === 'picker') savePicksDebounced();
}

function togglePick() {
  if (!state.selectedImage || appMode !== 'picker') return;

  const existing = state.assignments[state.selectedImage];
  if (existing) {
    // Already picked (named or unnamed) — unpick it
    delete state.reverseAssignments[existing];
    delete state.assignments[state.selectedImage];
  } else {
    // Pick without a view code
    state.assignments[state.selectedImage] = 'pick';
  }

  updateCardBadge(state.selectedImage);
  updatePickerList();
  updateButtons();
  updateStatusCount();
  savePicksDebounced();
  updateViewerPickButton();
  if (isViewerOpen()) {
    viewerNavigate(1);
  } else {
    autoAdvanceSelection();
  }
}

function updateViewerPickButton() {
  const btn = document.getElementById('viewer-pick');
  if (!btn) return;
  const isPicked = !!state.assignments[viewerCurrentPath || state.selectedImage];
  btn.textContent = isPicked ? '\u2715' : '\u2713';
  btn.classList.toggle('viewer-pick-active', isPicked);
  btn.style.display = appMode === 'picker' ? '' : 'none';

  // Show/hide delete button based on mode
  const delBtn = document.getElementById('viewer-delete');
  if (delBtn) delBtn.style.display = appMode === 'renamer' ? '' : 'none';
}

async function deleteCurrentImage() {
  if (appMode !== 'renamer') return;
  const target = viewerCurrentPath || state.selectedImage;
  if (!target) return;

  const name = state.images.find(i => i.path === target)?.name || target;
  if (!confirm(`Remove "${name}" from this tablet?\n\nThe file will be moved to the Recycle Bin.`)) return;

  const result = await window.api.deleteImage(target);
  if (!result.success) {
    alert(`Failed to remove: ${result.error}`);
    return;
  }

  // Remove from state
  delete state.assignments[target];
  const revKey = Object.entries(state.reverseAssignments).find(([, v]) => v === target)?.[0];
  if (revKey) delete state.reverseAssignments[revKey];

  const idx = state.images.findIndex(i => i.path === target);
  state.images.splice(idx, 1);

  // Remove thumbnail card
  const card = dom.thumbGrid.querySelector(`.thumb-card[data-path="${CSS.escape(target)}"]`);
  if (card) card.remove();

  // Navigate to next image in viewer or exit
  if (isViewerOpen()) {
    if (state.images.length === 0) {
      exitViewerMode();
    } else {
      const newIdx = Math.min(idx, state.images.length - 1);
      const newPath = state.images[newIdx].path;
      selectImage(newPath);
      loadViewerImage(newPath);
    }
  } else if (state.images.length > 0) {
    selectImage(state.images[Math.min(idx, state.images.length - 1)].path);
  }

  updateStructureDiagram();
  updateButtons();
  updateStatusCount();
  setStatus(`Removed ${name}`);
}

function autoAdvanceSelection() {
  const currentIdx = state.images.findIndex(img => img.path === state.selectedImage);

  for (let i = currentIdx + 1; i < state.images.length; i++) {
    if (!state.assignments[state.images[i].path]) {
      selectImage(state.images[i].path);
      return;
    }
  }
  for (let i = 0; i < currentIdx; i++) {
    if (!state.assignments[state.images[i].path]) {
      selectImage(state.images[i].path);
      return;
    }
  }
}

// === Keyboard ===
function onKeyDown(e) {
  // Ctrl shortcuts — always available
  if (e.ctrlKey && e.key.toLowerCase() === 's') {
    e.preventDefault();
    onConfirm();
    return;
  }
  if (e.ctrlKey && e.key.toLowerCase() === 'e') {
    e.preventDefault();
    onExportSelected();
    return;
  }

  // If focus is in an input/textarea, don't intercept single-key shortcuts
  // (except Escape, handled below, which should still close overlays).
  const inInput = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';
  if (inInput && e.key !== 'Escape') return;

  // Close overlays on Escape. Order matters: innermost overlay first so a
  // stacked overlay (e.g. ruler inside settings) dismisses the top layer.
  if (e.key === 'Escape') {
    if (!document.getElementById('result-preview-overlay').classList.contains('hidden')) { closeResultPreview(); return; }
    if (isViewerOpen()) {
      // Esc priority: cancel rect → deactivate tool → exit viewer
      if (previewTool.rectDisplay) { clearViewerRect(); e.preventDefault(); return; }
      if (previewTool.active) { setActiveTool(previewTool.active); e.preventDefault(); return; }
      exitViewerMode(); return;
    }
    if (!document.getElementById('ruler-overlay').classList.contains('hidden')) { closeRulerOverlay(); e.preventDefault(); return; }
    if (!document.getElementById('settings-overlay').classList.contains('hidden')) { closeSettings(); e.preventDefault(); return; }
    if (!document.getElementById('help-overlay').classList.contains('hidden')) { toggleHelp(); return; }
  }

  // Result preview mode
  if (!document.getElementById('result-preview-overlay').classList.contains('hidden')) {
    if (e.key === 'ArrowLeft') { navigateResultPreview(-1); e.preventDefault(); }
    else if (e.key === 'ArrowRight') { navigateResultPreview(1); e.preventDefault(); }
    else if (e.key.toLowerCase() === 'r') { setResultStatus('revision'); e.preventDefault(); }
    else if (e.key.toLowerCase() === 'u') { setResultStatus('updated'); e.preventDefault(); }
    else if (e.key === '0') { resetResultZoom(); e.preventDefault(); }
    return;
  }

  // Viewer mode: arrow navigation, rotation, tool shortcuts, assignments
  if (isViewerOpen()) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    const vKey = e.key.toLowerCase();

    // Handle pending combo in viewer
    if (state.comboPending) {
      if (COMBO_SECOND.has(vKey)) {
        const combo = state.comboPending + vKey;
        clearCombo();
        if (VIEW_CODES[combo]) {
          assignCurrentImage(combo);
          viewerNavigate(1);
        }
        e.preventDefault();
      } else {
        clearCombo();
      }
      return;
    }

    if (e.key === 'ArrowLeft' && e.shiftKey) {
      viewerRotate(-90); e.preventDefault();
    } else if (e.key === 'ArrowRight' && e.shiftKey) {
      viewerRotate(90); e.preventDefault();
    } else if (e.key === 'ArrowDown' && e.shiftKey) {
      viewerRotate(180); e.preventDefault();
    } else if (e.key === 'ArrowLeft') {
      viewerNavigate(-1); e.preventDefault();
    } else if (e.key === 'ArrowRight') {
      viewerNavigate(1); e.preventDefault();
    } else if (vKey === 's' && !e.ctrlKey) {
      setActiveTool('segment'); e.preventDefault();
    } else if (e.key === '0' && !e.ctrlKey) {
      resetViewerZoom(); e.preventDefault();
    } else if (e.key === 'Enter' && previewTool.active === 'segment' && segTool.currentMaskBase64) {
      applySegMask(); e.preventDefault();
    } else if (vKey === 'p' && appMode === 'picker') {
      togglePick(); e.preventDefault();
    } else if (vKey === 'u') {
      unassignCurrentImage(); e.preventDefault();
    } else if (SHORTCUT_MAP[vKey] && !e.ctrlKey && !e.altKey) {
      assignCurrentImage(SHORTCUT_MAP[vKey]);
      viewerNavigate(1);
      e.preventDefault();
    } else if (COMBO_FIRST.has(vKey) && !e.ctrlKey && !e.altKey) {
      state.comboPending = vKey;
      dom.comboIndicator.textContent = `${vKey.toUpperCase()} + ?`;
      dom.comboIndicator.classList.remove('hidden');
      state.comboTimer = setTimeout(clearCombo, 800);
      e.preventDefault();
    } else if (e.key === 'Escape') {
      exitViewerMode(); e.preventDefault();
    } else if (e.key === 'Delete' && appMode === 'renamer') {
      deleteCurrentImage(); e.preventDefault();
    }
    return;
  }

  if (!document.getElementById('help-overlay').classList.contains('hidden')) return;

  const key = e.key.toLowerCase();

  // Handle pending combo
  if (state.comboPending) {
    if (COMBO_SECOND.has(key)) {
      const combo = state.comboPending + key;
      clearCombo();
      if (VIEW_CODES[combo]) {
        assignCurrentImage(combo);
      }
      e.preventDefault();
      return;
    } else {
      clearCombo();
    }
  }

  // Start combo
  if (COMBO_FIRST.has(key) && !e.ctrlKey && !e.altKey) {
    state.comboPending = key;
    dom.comboIndicator.textContent = `${key.toUpperCase()} + ?`;
    dom.comboIndicator.classList.remove('hidden');
    state.comboTimer = setTimeout(clearCombo, 800);
    e.preventDefault();
    return;
  }

  // Single key shortcuts
  if (SHORTCUT_MAP[key] && !e.ctrlKey && !e.altKey) {
    assignCurrentImage(SHORTCUT_MAP[key]);
    e.preventDefault();
    return;
  }

  if (key === 'p' && appMode === 'picker') {
    togglePick();
    e.preventDefault();
  } else if (key === 'u') {
    unassignCurrentImage();
    e.preventDefault();
  } else if (e.key === 'Delete' && appMode === 'renamer') {
    deleteCurrentImage();
    e.preventDefault();
  } else if (e.key === 'ArrowLeft' && e.shiftKey) {
    rotateSelected(-90);
    e.preventDefault();
  } else if (e.key === 'ArrowRight' && e.shiftKey) {
    rotateSelected(90);
    e.preventDefault();
  } else if (e.key === 'ArrowDown' && e.shiftKey) {
    rotateSelected(180);
    e.preventDefault();
  } else if (e.key === 'ArrowLeft') {
    selectAdjacent(-1);
    e.preventDefault();
  } else if (e.key === 'ArrowRight') {
    selectAdjacent(1);
    e.preventDefault();
  } else if (e.key === 'Enter') {
    onConfirm();
    e.preventDefault();
  } else if (e.key === ' ') {
    if (state.selectedImage) enterViewerMode(state.selectedImage);
    e.preventDefault();
  }
}

function clearCombo() {
  state.comboPending = null;
  if (state.comboTimer) {
    clearTimeout(state.comboTimer);
    state.comboTimer = null;
  }
  dom.comboIndicator.classList.add('hidden');
}

// === Preview ===
// === Viewer Mode (replaces modal preview overlay) ===
let viewerCurrentPath = null;

function isViewerOpen() {
  return !dom.viewerMode.classList.contains('hidden');
}

async function enterViewerMode(imagePath) {
  if (!imagePath) return;
  // Opening an image is a fresh start — drop any leftover mask/box state
  clearSegState();
  viewerCurrentPath = imagePath;
  dom.thumbGridMode.classList.add('hidden');
  dom.viewerMode.classList.remove('hidden');
  await loadViewerImage(imagePath);
  updateToolInfo();
  updateViewerPickButton();
}

function exitViewerMode() {
  dom.viewerMode.classList.add('hidden');
  dom.thumbGridMode.classList.remove('hidden');
  dom.viewerImage.src = '';
  viewerCurrentPath = null;
  clearViewerRect();
  // Always deactivate the segment tool when leaving the viewer — next image
  // should start fresh without inherited mask state.
  if (previewTool.active === 'segment') setActiveTool('segment');
  // Clear the history panel — no image is viewed
  refreshSegHistory();
}

async function loadViewerImage(imagePath) {
  viewerCurrentPath = imagePath;
  dom.viewerImage.src = '';
  clearViewerRect();
  resetViewerZoom();
  if (previewTool.active === 'segment') {
    clearSegState();
  }
  // Refresh the segment history panel for whichever image is now open,
  // even if the tool isn't currently active.
  refreshSegHistory();

  const idx = state.images.findIndex(i => i.path === imagePath);
  const total = state.images.length;
  const name = state.images[idx]?.name || '';
  const code = state.assignments[imagePath];
  const viewName = code ? `${VIEW_CODES[code]} (_${code})` : 'unassigned';
  dom.viewerInfo.textContent = `${name}  |  ${viewName}  |  ${idx + 1}/${total}`;

  const dataUrl = await window.api.getFullImage(imagePath);
  if (dataUrl && viewerCurrentPath === imagePath) {
    dom.viewerImage.src = dataUrl;
  }
  updateToolInfo();
  updateViewerPickButton();
}

// === Viewer zoom + pan ===
// CSS-transform zoom on the image + overlay canvases (they move as one unit).
// Mouse wheel zooms centered on cursor. Middle-mouse drag pans. Double-click
// on the image (outside any active tool) or pressing "0" resets to fit.

const viewerZoom = {
  scale: 1,
  panX: 0,
  panY: 0,
  panning: false,
  panStartX: 0,
  panStartY: 0,
  panStartPanX: 0,
  panStartPanY: 0,
};

function applyViewerTransform() {
  const t = `translate(${viewerZoom.panX}px, ${viewerZoom.panY}px) scale(${viewerZoom.scale})`;
  // Anchor at top-left so the cursor-centered zoom math works correctly
  const origin = '0 0';
  if (dom.viewerImage) {
    dom.viewerImage.style.transformOrigin = origin;
    dom.viewerImage.style.transform = t;
  }
  const segC = document.getElementById('seg-canvas-container');
  if (segC) {
    segC.style.transformOrigin = origin;
    segC.style.transform = t;
  }
  const rectO = document.getElementById('viewer-rect-overlay');
  if (rectO) {
    rectO.style.transformOrigin = origin;
    rectO.style.transform = t;
  }
}

function resetViewerZoom() {
  viewerZoom.scale = 1;
  viewerZoom.panX = 0;
  viewerZoom.panY = 0;
  applyViewerTransform();
}

function onViewerWheel(e) {
  if (!isViewerOpen()) return;
  // Only zoom when cursor is over the stage (already true via event target)
  e.preventDefault();

  const stageRect = dom.viewerStage.getBoundingClientRect();
  const cx = e.clientX - stageRect.left;
  const cy = e.clientY - stageRect.top;

  const oldScale = viewerZoom.scale;
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  const newScale = Math.max(0.1, Math.min(10, oldScale * factor));
  if (newScale === oldScale) return;

  // Keep the point under the cursor stable as we zoom:
  // pan' = cursor - (cursor - pan) * (newScale / oldScale)
  viewerZoom.panX = cx - (cx - viewerZoom.panX) * (newScale / oldScale);
  viewerZoom.panY = cy - (cy - viewerZoom.panY) * (newScale / oldScale);
  viewerZoom.scale = newScale;
  applyViewerTransform();
}

function onViewerPanStart(e) {
  if (!isViewerOpen()) return;
  // Middle mouse always pans. Left mouse pans too, but only when no tool is
  // active (left-click with an active tool belongs to that tool, e.g. drawing
  // a bounding box for the segment tool).
  const isMiddle = e.button === 1;
  const isLeftNoTool = e.button === 0 && !previewTool.active;
  if (!isMiddle && !isLeftNoTool) return;

  e.preventDefault();
  viewerZoom.panning = true;
  viewerZoom.panStartX = e.clientX;
  viewerZoom.panStartY = e.clientY;
  viewerZoom.panStartPanX = viewerZoom.panX;
  viewerZoom.panStartPanY = viewerZoom.panY;
  document.body.style.cursor = 'grabbing';
}

function onViewerPanMove(e) {
  if (!viewerZoom.panning) return;
  viewerZoom.panX = viewerZoom.panStartPanX + (e.clientX - viewerZoom.panStartX);
  viewerZoom.panY = viewerZoom.panStartPanY + (e.clientY - viewerZoom.panStartY);
  applyViewerTransform();
}

function onViewerPanEnd() {
  if (!viewerZoom.panning) return;
  viewerZoom.panning = false;
  document.body.style.cursor = '';
}

// === Result preview zoom + pan (mirrors the viewer zoom/pan) ===
const resultZoom = {
  scale: 1,
  panX: 0,
  panY: 0,
  panning: false,
  panStartX: 0,
  panStartY: 0,
  panStartPanX: 0,
  panStartPanY: 0,
};

function applyResultTransform() {
  const img = document.getElementById('result-preview-image');
  if (!img) return;
  img.style.transformOrigin = '0 0';
  img.style.transform = `translate(${resultZoom.panX}px, ${resultZoom.panY}px) scale(${resultZoom.scale})`;
}

function resetResultZoom() {
  resultZoom.scale = 1;
  resultZoom.panX = 0;
  resultZoom.panY = 0;
  applyResultTransform();
}

function isResultPreviewOpen() {
  return !document.getElementById('result-preview-overlay').classList.contains('hidden');
}

function onResultWheel(e) {
  if (!isResultPreviewOpen()) return;
  e.preventDefault();

  const overlay = document.getElementById('result-preview-overlay');
  const img = document.getElementById('result-preview-image');
  if (!img) return;

  // The image is flex-centered in the overlay and has transform-origin: 0 0,
  // so the scaling origin is the image's layout top-left. Cursor coordinates
  // for the zoom-around-cursor math must be relative to that point, not the
  // overlay's top-left — otherwise zoom drifts toward the left edge.
  const ov = overlay.getBoundingClientRect();
  const imgLayoutLeft = ov.left + (ov.width - img.offsetWidth) / 2;
  const imgLayoutTop = ov.top + (ov.height - img.offsetHeight) / 2;
  const cx = e.clientX - imgLayoutLeft;
  const cy = e.clientY - imgLayoutTop;

  const oldScale = resultZoom.scale;
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  const newScale = Math.max(0.1, Math.min(10, oldScale * factor));
  if (newScale === oldScale) return;

  resultZoom.panX = cx - (cx - resultZoom.panX) * (newScale / oldScale);
  resultZoom.panY = cy - (cy - resultZoom.panY) * (newScale / oldScale);
  resultZoom.scale = newScale;
  applyResultTransform();
}

function onResultPanStart(e) {
  if (!isResultPreviewOpen()) return;
  // Ignore clicks on buttons / controls
  if (e.target.closest('button')) return;
  // Left or middle mouse pans
  if (e.button !== 0 && e.button !== 1) return;
  e.preventDefault();
  resultZoom.panning = true;
  resultZoom.moved = false;  // becomes true if mouse actually moves during the drag
  resultZoom.panStartX = e.clientX;
  resultZoom.panStartY = e.clientY;
  resultZoom.panStartPanX = resultZoom.panX;
  resultZoom.panStartPanY = resultZoom.panY;
  document.body.style.cursor = 'grabbing';
}

function onResultPanMove(e) {
  if (!resultZoom.panning) return;
  const dx = e.clientX - resultZoom.panStartX;
  const dy = e.clientY - resultZoom.panStartY;
  if (Math.abs(dx) > 2 || Math.abs(dy) > 2) resultZoom.moved = true;
  resultZoom.panX = resultZoom.panStartPanX + dx;
  resultZoom.panY = resultZoom.panStartPanY + dy;
  applyResultTransform();
}

function onResultPanEnd() {
  if (!resultZoom.panning) return;
  resultZoom.panning = false;
  document.body.style.cursor = '';
}

function viewerNavigate(direction) {
  if (!viewerCurrentPath) return;
  const idx = state.images.findIndex(i => i.path === viewerCurrentPath);
  const newIdx = idx + direction;
  if (newIdx >= 0 && newIdx < state.images.length) {
    const newPath = state.images[newIdx].path;
    selectImage(newPath);
    loadViewerImage(newPath);
  }
}

async function viewerRotate(degrees) {
  if (!viewerCurrentPath) return;
  dom.viewerInfo.textContent = `Rotating ${degrees}\u00B0...`;
  const newThumb = await window.api.rotateImage(viewerCurrentPath, degrees);
  if (newThumb) {
    const card = getCardForImage(viewerCurrentPath);
    if (card) card.querySelector('img').src = newThumb;
  }
  await loadViewerImage(viewerCurrentPath);
}

// === Rotation ===
async function rotateSingleImage(imagePath, degrees, card) {
  setStatus(`Rotating by ${degrees}\u00B0...`);
  const newThumb = await window.api.rotateImage(imagePath, degrees);
  if (newThumb && card) {
    card.querySelector('img').src = newThumb;
  }
  setStatus(`Rotated by ${degrees}\u00B0.`);
}

async function rotateSelected(degrees) {
  // Determine which images to rotate
  const paths = state.selectedImages.size > 1
    ? [...state.selectedImages]
    : (state.selectedImage ? [state.selectedImage] : []);

  if (paths.length === 0) return;

  if (paths.length === 1) {
    setStatus(`Rotating by ${degrees}\u00B0...`);
    const newThumb = await window.api.rotateImage(paths[0], degrees);
    if (newThumb) {
      const card = getCardForImage(paths[0]);
      if (card) card.querySelector('img').src = newThumb;
      setStatus(`Rotated by ${degrees}\u00B0.`);
    } else {
      setStatus('Rotation failed.');
    }
  } else {
    setStatus(`Rotating ${paths.length} images by ${degrees}\u00B0...`);
    const results = await window.api.rotateImagesBatch(paths, degrees);
    for (const result of results) {
      if (result.thumbnail) {
        const card = getCardForImage(result.path);
        if (card) card.querySelector('img').src = result.thumbnail;
      }
    }
    const okCount = results.filter(r => r.status === 'ok').length;
    setStatus(`Rotated ${okCount} image(s) by ${degrees}\u00B0.`);
  }
}

// === Confirm / Reset ===
async function onConfirm() {
  if (appMode === 'picker') {
    await onExportSelected();
    return;
  }

  const count = Object.keys(state.assignments).length;
  if (count === 0) {
    alert('No images have been assigned.');
    return;
  }

  let sub;
  if (appMode === 'renamer' && selectedTreeIndex >= 0) {
    sub = selectedTreeFolders[selectedTreeIndex];
  } else {
    sub = state.subfolders[state.currentIndex];
  }
  if (!sub) return;
  const tabletId = sub.name;
  const normalizedId = tabletId.replace(/(\w+)\s+(\d+)/g, '$1.$2');

  // Build summary: assigned files
  const assignedLines = Object.entries(state.assignments)
    .sort(([, a], [, b]) => a.localeCompare(b))
    .map(([imgPath, code]) => {
      const oldName = state.images.find(i => i.path === imgPath)?.name || '';
      const ext = oldName.substring(oldName.lastIndexOf('.')).toLowerCase();
      const newName = `${normalizedId}_${code}${ext}`;
      if (oldName.toLowerCase() === newName.toLowerCase()) return null; // skip same name
      return `  ${oldName}  \u2192  ${newName}`;
    })
    .filter(Boolean);

  // Build summary: unassigned files
  const assignedPaths = new Set(Object.keys(state.assignments));
  const unassignedImages = state.images.filter(i => !assignedPaths.has(i.path));
  const unassignedLines = unassignedImages.map((img, idx) => {
    const suffix = unassignedImages.length === 1 ? 'unassigned' : `unassigned_${String(idx + 1).padStart(2, '0')}`;
    const ext = img.name.substring(img.name.lastIndexOf('.')).toLowerCase();
    return `  ${img.name}  \u2192  ${normalizedId}_${suffix}${ext}`;
  });

  // Nothing to change?
  if (assignedLines.length === 0 && unassignedLines.length === 0) {
    alert('All files already have the correct names. Nothing to change.');
    return;
  }

  let msg = `Save ${count} assigned file(s) in "${tabletId}"?\n`;
  if (assignedLines.length > 0) {
    msg += `\nAssigned:\n${assignedLines.join('\n')}`;
  }
  if (appMode !== 'renamer' && unassignedLines.length > 0) {
    msg += `\n\nUnassigned (${unassignedLines.length}):\n${unassignedLines.join('\n')}`;
  }

  const ok = confirm(msg);
  if (!ok) return;

  setStatus('Renaming...');

  // In renamer mode, only rename assigned files (leave others untouched)
  // In picker mode, rename all (unassigned get _unassigned suffix)
  const allPaths = appMode === 'renamer'
    ? Object.keys(state.assignments)
    : state.images.map(i => i.path);
  const results = await window.api.renameFiles(sub.path, state.assignments, tabletId, allPaths);

  const okCount = results.filter(r => r.status === 'ok' || r.status === 'skipped').length;
  const errCount = results.filter(r => r.status === 'error').length;

  if (errCount > 0) {
    const errorDetails = results
      .filter(r => r.status === 'error')
      .map(r => `${r.oldName}: ${r.error}`)
      .join('\n');
    alert(`Renamed ${okCount} file(s), ${errCount} error(s):\n\n${errorDetails}`);
  } else {
    setStatus(`Renamed ${okCount} file(s) successfully.`);
  }

  // Re-scan and reload the current folder (stay here, don't auto-advance)
  if (appMode === 'renamer' && selectedTreeIndex >= 0) {
    await buildSelectedTree();
    await loadSelectedFolder(selectedTreeIndex);
  } else {
    const scanResult = await window.api.scanFolder(state.rootFolder);
    state.subfolders = scanResult.subfolders;
    buildTreeView();
    loadResults();
    loadCurrentSubfolder();
  }
}

function onReset() {
  if (Object.keys(state.assignments).length === 0) return;
  if (!confirm('Clear all assignments for this folder?')) return;

  for (const imgPath of Object.keys(state.assignments)) {
    updateCardBadge(imgPath, true);
  }
  state.assignments = {};
  state.reverseAssignments = {};
  updateStructureDiagram();
  updateButtons();
  updateStatusCount();
}

// === UI Updates ===
function getCardForImage(imagePath) {
  return dom.thumbGrid.querySelector(`.thumb-card[data-path="${CSS.escape(imagePath)}"]`);
}

function updateCardBadge(imagePath, forceRemove = false) {
  const card = getCardForImage(imagePath);
  if (!card) return;

  const code = forceRemove ? null : state.assignments[imagePath];
  const badge = card.querySelector('.thumb-badge');

  if (code === 'pick') {
    badge.textContent = '\u2713';
    card.classList.add('assigned');
  } else if (code) {
    badge.textContent = `_${code}`;
    card.classList.add('assigned');
  } else {
    badge.textContent = '';
    card.classList.remove('assigned');
  }
}

function updateStructureDiagram() {
  document.querySelectorAll('.slot[data-code]').forEach(slot => {
    const code = slot.dataset.code;
    const imgPath = state.reverseAssignments[code];

    // Remove old filename badge
    const oldBadge = slot.querySelector('.slot-filename');
    if (oldBadge) oldBadge.remove();

    if (imgPath) {
      slot.classList.add('assigned');

      // Show filename between label and shortcut
      const fname = state.images.find(i => i.path === imgPath)?.name || '';
      const badge = document.createElement('span');
      badge.className = 'slot-filename';
      badge.textContent = fname;
      // Insert before shortcut
      const shortcut = slot.querySelector('.slot-shortcut');
      slot.insertBefore(badge, shortcut);
    } else {
      slot.classList.remove('assigned');
    }

    if (slot.classList.contains('mirror-slot') && imgPath) {
      slot.style.opacity = '0.7';
    } else if (slot.classList.contains('mirror-slot')) {
      slot.style.opacity = '0.5';
    }
  });
}

function updateButtons() {
  const hasAssignments = Object.keys(state.assignments).length > 0;
  dom.btnConfirm.disabled = !hasAssignments;
  dom.btnReset.disabled = !hasAssignments;
}

function setStatus(text) {
  dom.statusText.textContent = text;
}

function updateStatusCount() {
  const total = state.images.length;
  const assigned = Object.keys(state.assignments).length;
  const selCount = state.selectedImages.size;

  let selText;
  if (selCount > 1) {
    selText = `${selCount} images selected`;
  } else if (state.selectedImage) {
    const name = state.images.find(i => i.path === state.selectedImage)?.name || 'none';
    const code = state.assignments[state.selectedImage];
    const codePart = code === 'pick' ? ' \u2713 picked'
      : code ? ` \u2192 _${code} (${VIEW_CODES[code]})` : '';
    selText = `Selected: ${name}${codePart}`;
  } else {
    selText = 'No selection';
  }

  dom.statusText.textContent = selText;
  dom.statusCount.textContent = appMode === 'picker'
    ? `${assigned} / ${total} picked`
    : `${assigned} / ${total} assigned`;
}

// === Results System ===
const resultsState = {
  results: [],
  currentIndex: 0,
  selectedResult: null,
  reviewStatus: {},
  hasResults: false,
  view: 'dashboard',
};

function setResultView(view) {
  if (view !== 'dashboard' && view !== 'detail') return;
  resultsState.view = view;
  const dashboardEl = document.getElementById('result-view-dashboard');
  const detailEl = document.getElementById('result-view-detail');
  if (dashboardEl) dashboardEl.classList.toggle('hidden', view !== 'dashboard');
  if (detailEl) detailEl.classList.toggle('hidden', view !== 'detail');
  document.querySelectorAll('.result-view-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.resultView === view);
  });
}

let activeTab = 'structure';

function getResultsRoot() {
  if (appMode === 'renamer') {
    return customExportFolder || (state.rootFolder + '/_Selected');
  }
  return state.rootFolder;
}

// === Live collaboration: periodic refresh of review_status.json ===
// Re-reads the shared status file every 10 seconds so changes from other
// users (assignments, status updates) appear automatically.
let statusRefreshInterval = null;

function startStatusRefresh() {
  stopStatusRefresh();
  statusRefreshInterval = setInterval(async () => {
    if (appMode !== 'renamer') return;
    const root = getResultsRoot();
    if (!root) return;
    try {
      const fresh = await window.api.loadReviewStatus(root);
      // Only update if something actually changed (avoid unnecessary redraws)
      const freshStr = JSON.stringify(fresh);
      const currentStr = JSON.stringify(resultsState.reviewStatus);
      if (freshStr !== currentStr) {
        resultsState.reviewStatus = fresh;
        updateTreeStatusIcons();
        updateResultSummary();
      }
    } catch (e) { /* ignore — file might be mid-sync on Drive */ }
  }, 10000);
}

function stopStatusRefresh() {
  if (statusRefreshInterval) {
    clearInterval(statusRefreshInterval);
    statusRefreshInterval = null;
  }
}

async function loadResults() {
  if (!state.rootFolder) return;

  const resultsRoot = getResultsRoot();
  const data = await window.api.scanResults(resultsRoot);
  resultsState.results = data.results;
  resultsState.hasResults = data.hasResults;

  if (data.hasResults) {
    resultsState.reviewStatus = await window.api.loadReviewStatus(resultsRoot);
  }

  try {
    const projectNotes = await window.api.loadProjectNotes(resultsRoot);
    const dashNotesEl = document.getElementById('dashboard-notes');
    if (dashNotesEl) dashNotesEl.value = projectNotes?.notes || '';
  } catch (err) {
    console.error('loadProjectNotes failed:', err);
  }

  updateResultsTab();
  updateTreeStatusIcons();
}

function updateResultsTab() {
  updateResultSummary();

  // If results tab is active, show result thumbnails in left panel
  if (activeTab === 'results') {
    showResultThumbnails();
  }
}

function showResultThumbnails() {
  dom.thumbGrid.innerHTML = '';

  // Sync with current subfolder if possible
  if (state.subfolders.length > 0 && state.currentIndex >= 0) {
    const currentName = state.subfolders[state.currentIndex]?.name;
    const matchIdx = resultsState.results.findIndex(r => r.name === currentName);
    if (matchIdx >= 0) resultsState.currentIndex = matchIdx;
  }

  for (let i = 0; i < resultsState.results.length; i++) {
    const result = resultsState.results[i];
    const rawReview = resultsState.reviewStatus[result.name];
    const review = getEffectiveReview(rawReview, result.variant);
    const statusClass = review?.status ? ` ${review.status}` : '';

    const card = document.createElement('div');
    card.className = `result-card${statusClass}`;
    card.dataset.index = i;

    const badge = document.createElement('div');
    badge.className = 'result-badge';
    badge.textContent = statusBadge(review?.status);
    card.appendChild(badge);

    const imgEl = document.createElement('img');
    imgEl.alt = result.name;
    card.appendChild(imgEl);

    const name = document.createElement('div');
    name.className = 'result-name';
    name.textContent = result.name;
    card.appendChild(name);

    if (result.variant === 'print') {
      card.classList.add('variant-print');
      const chip = document.createElement('div');
      chip.className = 'result-variant-chip';
      chip.textContent = 'Print';
      card.appendChild(chip);
    }

    card.addEventListener('click', () => {
      resultsState.currentIndex = i;
      resultsState.selectedResult = result;
      updateResultSelection();
      showResultNotes(result);
      showResultMetadata(result);
      setResultView('detail');
      const emptyEl = document.getElementById('detail-empty');
      if (emptyEl) emptyEl.classList.add('hidden');
    });

    card.addEventListener('dblclick', () => {
      resultsState.currentIndex = i;
      openResultPreview(i);
    });

    card.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      window.api.revealInExplorer(result.jpgPath);
    });

    dom.thumbGrid.appendChild(card);

    // Load thumbnail async
    (async () => {
      const thumb = await window.api.getResultThumbnail(result.jpgPath);
      if (thumb) imgEl.src = thumb;
    })();
  }

  // Select current
  updateResultSelection();
  const current = resultsState.results[resultsState.currentIndex];
  if (current) {
    showResultNotes(current);
  } else {
    const notesEl = document.getElementById('result-notes');
    if (notesEl) {
      notesEl.value = '';
      notesEl.disabled = true;
      notesEl.placeholder = 'Select a tablet thumbnail to add notes...';
    }
  }
}

function updateResultSelection() {
  document.querySelectorAll('.result-card').forEach(card => {
    card.classList.toggle('selected', parseInt(card.dataset.index) === resultsState.currentIndex);
  });
  const active = document.querySelector('.result-card.selected');
  if (active) active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function showResultNotes(result) {
  const review = resultsState.reviewStatus[result.name] || {};
  const notesEl = document.getElementById('result-notes');
  notesEl.value = review.notes || '';
  notesEl.disabled = false;
  notesEl.placeholder = `Notes for ${result.name}...`;
  const emptyEl = document.getElementById('detail-empty');
  if (emptyEl) emptyEl.classList.add('hidden');
}

let metadataReqId = 0;
function formatBytes(n) {
  if (!n && n !== 0) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
async function showResultMetadata(result) {
  const el = document.getElementById('result-metadata');
  if (!el) return;
  const reqId = ++metadataReqId;
  el.classList.remove('hidden');
  el.innerHTML = `<div class="meta-loading">Loading metadata\u2026</div>`;

  const meta = await window.api.getResultMetadata(result.jpgPath);
  if (reqId !== metadataReqId) return;

  const fileRows = [];
  fileRows.push(['File', `${result.name}.jpg`]);
  if (meta.width && meta.height) fileRows.push(['Dimensions', `${meta.width} \u00d7 ${meta.height} px`]);
  if (meta.sizeBytes) fileRows.push(['Size', formatBytes(meta.sizeBytes)]);
  if (meta.format) fileRows.push(['Format', meta.format.toUpperCase()]);
  if (meta.modifiedAt) fileRows.push(['Modified', new Date(meta.modifiedAt).toLocaleString()]);

  const LABELS = {
    // EXIF
    Make: 'Make', Model: 'Model', Software: 'Software',
    Artist: 'Artist', Copyright: 'Copyright',
    ImageDescription: 'Image Description',
    DateTimeOriginal: 'Date Taken', DateTime: 'Date Modified',
    XResolution: 'X Resolution', YResolution: 'Y Resolution',
    ResolutionUnit: 'Resolution Unit',
    // XMP (Dublin Core + others)
    title: 'Title (dc)', creator: 'Creator (dc)', description: 'Description (dc)',
    rights: 'Rights (dc)', subject: 'Subject / Keywords (dc)',
    identifier: 'Identifier (dc)', publisher: 'Publisher (dc)',
    date: 'Date (dc)', format: 'Format (dc)', type: 'Type (dc)',
    CreatorTool: 'Creator Tool (xmp)', CreateDate: 'Create Date (xmp)',
    ModifyDate: 'Modify Date (xmp)', MetadataDate: 'Metadata Date (xmp)',
    Marked: 'Marked (xmpRights)', UsageTerms: 'Usage Terms (xmpRights)',
    WebStatement: 'Web Statement (xmpRights)',
    Credit: 'Credit (photoshop)', Source: 'Source (photoshop)',
    Headline: 'Headline (photoshop)', Instructions: 'Instructions (photoshop)',
    ObjectWidthCm: 'Object Width (ebl)', ObjectLengthCm: 'Object Length (ebl)',
    PixelsPerCm: 'Pixels / cm (ebl)',
    // IPTC
    Byline: 'Byline', BylineTitle: 'Byline Title',
    CopyrightNotice: 'Copyright Notice', Caption: 'Caption',
    Keywords: 'Keywords', ObjectName: 'Object Name',
  };

  const renderRow = ([k, v]) =>
    `<div class="meta-row"><span class="meta-key">${escapeHtml(k)}</span><span class="meta-val">${escapeHtml(v)}</span></div>`;

  const renderSection = (label, rows) => rows.length ? `
    <div class="meta-section-label">${escapeHtml(label)}</div>
    <div class="meta-section">${rows.map(renderRow).join('')}</div>
  ` : '';

  const sectionRows = (obj) => Object.entries(obj).map(([k, v]) => [LABELS[k] || k, String(v)]);

  const parts = [];
  parts.push(renderSection('File', fileRows));

  if (meta.sections) {
    for (const name of ['EXIF', 'XMP', 'IPTC']) {
      const block = meta.sections[name];
      if (block && Object.keys(block).length > 0) {
        parts.push(renderSection(name, sectionRows(block)));
      }
    }
  }

  // Diagnostic footer: only visible if exifr returned nothing or erred out,
  // so we can see what's actually being parsed.
  if (!meta.sections) {
    if (meta._exifrError) {
      parts.push(`<div class="meta-section-label">exifr error</div>
        <div class="meta-section"><div class="meta-val">${escapeHtml(meta._exifrError)}</div></div>`);
    } else if (meta._rawKeys) {
      parts.push(`<div class="meta-section-label">Raw keys (no classification matched)</div>
        <div class="meta-section"><div class="meta-val">${escapeHtml(meta._rawKeys.join(', ') || '(empty)')}</div></div>`);
    } else {
      parts.push(`<div class="meta-section-label">No metadata found</div>`);
    }
  }

  el.innerHTML = parts.join('');
}

// Result preview overlay
async function openResultPreview(index) {
  resultsState.currentIndex = index;
  const overlay = document.getElementById('result-preview-overlay');
  overlay.classList.remove('hidden');
  resetResultZoom();
  await loadResultPreviewImage(index);
}

async function loadResultPreviewImage(index) {
  const result = resultsState.results[index];
  if (!result) return;
  resultsState.currentIndex = index;

  const review = resultsState.reviewStatus[result.name];
  updateResultPreviewUI(review);

  const imgEl = document.getElementById('result-preview-image');
  imgEl.src = '';
  resetResultZoom();
  const dataUrl = await window.api.getFullImage(result.jpgPath);
  if (dataUrl) imgEl.src = dataUrl;
}

function navigateResultPreview(direction) {
  const newIdx = resultsState.currentIndex + direction;
  if (newIdx >= 0 && newIdx < resultsState.results.length) {
    loadResultPreviewImage(newIdx);
    updateResultSelection();
  }
}

function closeResultPreview() {
  document.getElementById('result-preview-overlay').classList.add('hidden');
  document.getElementById('result-preview-image').src = '';
}

// Jump from a result preview back to the tablet's _Selected/ images so the
// user can re-edit (apply SAM, fix assignments, re-export, etc.).
async function editSelectedForCurrentResult() {
  const result = resultsState.results[resultsState.currentIndex];
  if (!result) return;

  closeResultPreview();

  // Ensure we're in Renamer mode (the _Selected/ tree)
  if (appMode !== 'renamer') {
    switchMode('renamer');
    // Wait for the tree to rebuild
    await new Promise(r => setTimeout(r, 50));
  }

  // Find the matching _Selected/ tablet folder by name
  // Rebuild the tree so we have fresh selectedTreeFolders
  await buildSelectedTree();
  const idx = selectedTreeFolders.findIndex(f => f.name === result.name);
  if (idx < 0) {
    setStatus(`No _Selected/ folder found for ${result.name}`);
    return;
  }

  // Load that tablet and switch to Tools tab for immediate editing
  await loadSelectedFolder(idx);
  document.querySelector('.right-tab[data-tab="tools"]')?.click();
}

// Set or toggle a result's review status. Clicking the same status clears it.
async function setResultStatus(newStatus) {
  const result = resultsState.results[resultsState.currentIndex];
  if (!result) return;

  const existing = resultsState.reviewStatus[result.name] || {};

  if (existing.status === newStatus) {
    // Toggle off — clear status but keep notes
    delete existing.status;
    delete existing.reviewedAt;
    if (!existing.notes) {
      delete resultsState.reviewStatus[result.name];
    }
  } else {
    resultsState.reviewStatus[result.name] = {
      ...existing,
      status: newStatus,
      reviewedAt: new Date().toISOString(),
    };
  }

  await window.api.saveReviewStatus(getResultsRoot(), resultsState.reviewStatus);

  const review = resultsState.reviewStatus[result.name];
  updateResultPreviewUI(review);

  // Update thumbnail card classes and badge
  const card = document.querySelector(`.result-card[data-index="${resultsState.currentIndex}"]`);
  if (card) {
    card.classList.remove('revision', 'updated', 'sent');
    if (review?.status) card.classList.add(review.status);
    const badge = card.querySelector('.result-badge');
    if (badge) badge.textContent = statusBadge(review?.status);
  }

  updateTreeStatusIcons();
  updateResultSummary();
}

function updateResultPreviewUI(review) {
  const result = resultsState.results[resultsState.currentIndex];
  if (!result) return;

  // Update buttons
  document.getElementById('result-toggle-revision').classList.toggle('active', review?.status === 'revision');
  document.getElementById('result-toggle-updated').classList.toggle('active', review?.status === 'updated');
  document.getElementById('result-toggle-sent').classList.toggle('active', review?.status === 'sent');

  // Update info text
  const statusLabels = { revision: '  [REVISION]', updated: '  [UPDATED]', sent: '  [SENT]' };
  const statusLabel = statusLabels[review?.status] || '';
  const total = resultsState.results.length;
  document.getElementById('result-preview-info').textContent =
    `${result.name}${statusLabel}  |  ${resultsState.currentIndex + 1}/${total}  |  \u2190\u2192 navigate  |  R revision  |  U updated  |  Esc close`;
}

function statusBadge(status) {
  if (status === 'updated') return '\uD83D\uDFE2';   // 🟢
  if (status === 'sent') return '\uD83D\uDFE1';      // 🟡
  if (status === 'finished') return '\u26AA';        // ⚪ (filled white circle)
  return '\uD83D\uDD34';                              // 🔴
}

const STATUS_OPTIONS = [
  { key: null,         label: 'Clear',    badge: '\u25CB'  },  // ○ empty
  { key: 'updated',    label: 'Ready',    badge: '\uD83D\uDFE2' },
  { key: 'revision',   label: 'Revision', badge: '\uD83D\uDD34' },
  { key: 'sent',       label: 'Sent',     badge: '\uD83D\uDFE1' },
  { key: 'finished',   label: 'Finished', badge: '\u26AA' },
];

function updateResultSummary() {
  // Count per-result (variant-aware) so a tablet with different statuses on
  // its digital vs. print variants contributes one tick per variant.
  const effective = resultsState.results.map(r =>
    getEffectiveReview(resultsState.reviewStatus[r.name], r.variant));
  const revCount = effective.filter(r => r.status === 'revision').length;
  const updCount = effective.filter(r => r.status === 'updated').length;
  const sentCount = effective.filter(r => r.status === 'sent').length;
  const finCount = effective.filter(r => r.status === 'finished').length;
  const parts = [`${resultsState.results.length} results`];
  if (finCount) parts.push(`${finCount} finished`);
  if (sentCount) parts.push(`${sentCount} sent`);
  if (revCount) parts.push(`${revCount} revision`);
  if (updCount) parts.push(`${updCount} updated`);
  document.getElementById('result-summary').textContent = parts.join('  |  ');
}

async function saveCurrentNotes() {
  const result = resultsState.results[resultsState.currentIndex];
  if (!result) return;

  const notes = document.getElementById('result-notes').value.trim();
  const existing = resultsState.reviewStatus[result.name] || {};

  if (notes) {
    resultsState.reviewStatus[result.name] = {
      ...existing,
      notes,
      reviewedAt: new Date().toISOString(),
    };
  } else if (existing.notes) {
    delete existing.notes;
    if (!existing.status) {
      delete resultsState.reviewStatus[result.name];
    }
  }

  await window.api.saveReviewStatus(getResultsRoot(), resultsState.reviewStatus);
  setStatus(`Notes saved for ${result.name}.`);
}

async function saveDashboardNotes() {
  if (!state.rootFolder) return;
  const notes = document.getElementById('dashboard-notes').value;
  try {
    await window.api.saveProjectNotes(getResultsRoot(), notes);
    setStatus('General notes saved.');
  } catch (err) {
    console.error('saveProjectNotes failed:', err);
  }
}

function updateTreeStatusIcons() {
  if (appMode === 'picker') return;
  document.querySelectorAll('.tree-item').forEach(item => {
    const idx = parseInt(item.dataset.selectedIndex);
    const sub = selectedTreeFolders[idx];
    if (!sub) return;

    const oldIcon = item.querySelector('.tree-status');
    if (oldIcon) oldIcon.remove();
    const oldAssign = item.querySelector('.tree-assign');
    if (oldAssign) oldAssign.remove();

    const review = resultsState.reviewStatus[sub.name];
    const assignedTo = review?.assignedTo || null;
    const isMine = assignedTo === currentUserName;
    const isOther = assignedTo && !isMine;

    // Assignment indicator (before the status icon)
    if (assignedTo) {
      const assignEl = document.createElement('span');
      assignEl.className = 'tree-assign';
      if (isMine) {
        assignEl.textContent = '\u270B'; // ✋ (me)
        assignEl.title = 'Assigned to you';
      } else {
        assignEl.textContent = '\uD83D\uDD12'; // 🔒
        assignEl.title = `Assigned to ${assignedTo}`;
      }
      item.appendChild(assignEl);
    }

    // Status icon
    const icon = document.createElement('span');
    icon.className = 'tree-status';

    if (review?.status) {
      icon.textContent = statusBadge(review.status);
      icon.title = `Status: ${review.status}` + (assignedTo ? ` | ${assignedTo}` : '') + ' — click to change';
    } else {
      icon.textContent = '\u25CB';  // empty circle
      icon.title = 'Click to set status';
      icon.classList.add('tree-status-empty');
    }

    // Dim items assigned to someone else
    item.style.opacity = isOther ? '0.5' : '';

    icon.addEventListener('click', (e) => {
      e.stopPropagation();
      showStatusDropdown(icon, sub.name);
    });
    item.appendChild(icon);
  });

  updateProcessButton();
}

async function setTabletStatus(tabletName, newStatus) {
  const existing = resultsState.reviewStatus[tabletName] || {};

  if (newStatus) {
    resultsState.reviewStatus[tabletName] = {
      ...existing,
      status: newStatus,
      reviewedAt: new Date().toISOString(),
    };
  } else {
    delete existing.status;
    delete existing.reviewedAt;
    if (!existing.notes) {
      delete resultsState.reviewStatus[tabletName];
    }
  }

  await window.api.saveReviewStatus(getResultsRoot(), resultsState.reviewStatus);
  updateTreeStatusIcons();
  updateResultSummary();

  // Update the result card if visible
  const resultIdx = resultsState.results.findIndex(r => r.name === tabletName);
  if (resultIdx >= 0) {
    const card = document.querySelector(`.result-card[data-index="${resultIdx}"]`);
    if (card) {
      const review = resultsState.reviewStatus[tabletName];
      card.classList.remove('revision', 'updated', 'sent', 'finished');
      if (review?.status) card.classList.add(review.status);
      const badge = card.querySelector('.result-badge');
      if (badge) badge.textContent = statusBadge(review?.status);
    }
  }
}

// Popup dropdown near the clicked icon listing all status options
function showStatusDropdown(anchorEl, tabletName) {
  // Close any existing popup
  document.querySelectorAll('.status-dropdown').forEach(el => el.remove());

  const review = resultsState.reviewStatus[tabletName] || {};
  const existing = review.status || null;
  const assignedTo = review.assignedTo || null;
  const isMine = assignedTo === currentUserName;
  const isOther = assignedTo && !isMine;
  const rect = anchorEl.getBoundingClientRect();

  const menu = document.createElement('div');
  menu.className = 'status-dropdown';
  menu.style.left = `${rect.left}px`;
  // Position below the icon by default; flip above if it would go off-screen
  menu.style.top = `${rect.bottom + 4}px`;
  menu.style.visibility = 'hidden'; // measure first, then show

  // Assignment section at the top
  if (!assignedTo) {
    const assignRow = document.createElement('div');
    assignRow.className = 'status-dropdown-item';
    assignRow.innerHTML = `<span class="status-dropdown-badge">\uD83D\uDCCC</span><span>Assign to me</span>`;
    assignRow.addEventListener('click', async (e) => {
      e.stopPropagation();
      menu.remove();
      await assignTablet(tabletName, currentUserName);
    });
    menu.appendChild(assignRow);
  } else if (isMine) {
    const releaseRow = document.createElement('div');
    releaseRow.className = 'status-dropdown-item';
    releaseRow.innerHTML = `<span class="status-dropdown-badge">\uD83D\uDD13</span><span>Release</span>`;
    releaseRow.addEventListener('click', async (e) => {
      e.stopPropagation();
      menu.remove();
      await assignTablet(tabletName, null);
    });
    menu.appendChild(releaseRow);
  } else {
    const infoRow = document.createElement('div');
    infoRow.className = 'status-dropdown-item';
    infoRow.style.opacity = '0.6';
    infoRow.style.cursor = 'default';
    infoRow.innerHTML = `<span class="status-dropdown-badge">\uD83D\uDD12</span><span>Assigned to ${assignedTo}</span>`;
    menu.appendChild(infoRow);
  }

  // Divider
  const divider = document.createElement('div');
  divider.style.borderTop = '1px solid var(--border)';
  divider.style.margin = '3px 0';
  menu.appendChild(divider);

  // Status options (only clickable if unassigned or assigned to me)
  for (const opt of STATUS_OPTIONS) {
    const row = document.createElement('div');
    row.className = 'status-dropdown-item' + (opt.key === existing ? ' active' : '');
    if (isOther) row.style.opacity = '0.4';
    row.innerHTML = `<span class="status-dropdown-badge">${opt.badge}</span><span>${opt.label}</span>`;
    row.addEventListener('click', async (e) => {
      e.stopPropagation();
      menu.remove();
      if (isOther) return; // can't change someone else's status
      await setTabletStatus(tabletName, opt.key);
    });
    menu.appendChild(row);
  }

  document.body.appendChild(menu);

  // Flip above if the menu would go below the viewport
  const menuRect = menu.getBoundingClientRect();
  if (menuRect.bottom > window.innerHeight) {
    menu.style.top = `${rect.top - menuRect.height - 4}px`;
  }
  // Also keep it on-screen horizontally
  if (menuRect.right > window.innerWidth) {
    menu.style.left = `${window.innerWidth - menuRect.width - 8}px`;
  }
  menu.style.visibility = '';

  const closeOnOutside = (e) => {
    if (!menu.contains(e.target)) {
      menu.remove();
      document.removeEventListener('mousedown', closeOnOutside);
    }
  };
  setTimeout(() => document.addEventListener('mousedown', closeOnOutside), 0);
}

async function assignTablet(tabletName, userName) {
  const existing = resultsState.reviewStatus[tabletName] || {};
  if (userName) {
    resultsState.reviewStatus[tabletName] = {
      ...existing,
      assignedTo: userName,
      assignedAt: new Date().toISOString(),
    };
  } else {
    delete existing.assignedTo;
    delete existing.assignedAt;
    if (!existing.status && !existing.notes) {
      delete resultsState.reviewStatus[tabletName];
    }
  }
  await window.api.saveReviewStatus(getResultsRoot(), resultsState.reviewStatus);
  updateTreeStatusIcons();
  updateResultSummary();
}

// === Settings ===
let currentProjectName = '';

async function openSettings() {
  const config = await window.api.getStitcherConfig();
  await loadProjectList(config.activeProject);
  document.getElementById('settings-overlay').classList.remove('hidden');
}

async function loadProjectList(selectName) {
  const projects = await window.api.listProjects();
  const select = document.getElementById('setting-project-select');
  select.innerHTML = '';

  // Split "General (...)" projects into one optgroup and museum/institution
  // projects into another. <optgroup> renders a horizontal separator with
  // a label — the cleanest native way to divide a <select>.
  const general = projects.filter(p => /^general\b/i.test(p.name));
  const museums = projects.filter(p => !/^general\b/i.test(p.name));

  const makeOpt = (p) => {
    const opt = document.createElement('option');
    opt.value = p.name;
    opt.textContent = p.name;
    return opt;
  };

  if (general.length > 0) {
    const g = document.createElement('optgroup');
    g.label = 'General';
    for (const p of general) g.appendChild(makeOpt(p));
    select.appendChild(g);
  }
  if (museums.length > 0) {
    const g = document.createElement('optgroup');
    g.label = 'Projects';
    for (const p of museums) g.appendChild(makeOpt(p));
    select.appendChild(g);
  }

  const DEFAULT_PROJECT = 'General (black background)';
  if (selectName && projects.some(p => p.name === selectName)) {
    select.value = selectName;
  } else if (projects.some(p => p.name === DEFAULT_PROJECT)) {
    select.value = DEFAULT_PROJECT;
  } else if (projects.length > 0) {
    select.value = projects[0].name;
  }

  await loadProjectFields(select.value);

  select.addEventListener('change', async () => {
    await loadProjectFields(select.value);
  });
}

async function loadProjectFields(projectName) {
  currentProjectName = projectName;
  const project = await window.api.getProject(projectName);
  if (!project) return;

  document.getElementById('setting-photographer').value = project.photographer || '';
  document.getElementById('setting-institution').value = project.institution || '';
  document.getElementById('setting-measurements').value = project.measurements_file || '';
  document.getElementById('setting-output-type').value = project.output_type || 'digital';

  // Resolve the project's ruler config into our selection convention.
  // Built-in project JSONs use either:
  //   ruler_file : "Name.svg"                        → single fixed ruler
  //   ruler_files: { "1cm": "...", "2cm": "...", ... } → adaptive set
  // Our UI uses `file:<path>` and `set:<groupId>` strings in the hidden
  // input. populateRulerGrid() already matches bare filenames against the
  // built-in absolute paths, so `file:Name.svg` works fine.
  let rulerSelection = '';
  if (project.ruler_set) {
    rulerSelection = `set:${project.ruler_set}`;
  } else if (project.ruler_files && typeof project.ruler_files === 'object') {
    const sample = project.ruler_files['1cm'] || project.ruler_files['2cm']
                || project.ruler_files['5cm'] || Object.values(project.ruler_files)[0] || '';
    if (/^BM_/i.test(sample)) rulerSelection = 'set:bm_donated';
    else if (/^Black_/i.test(sample)) rulerSelection = 'set:black_jena';
  } else if (project.ruler_file) {
    rulerSelection = `file:${project.ruler_file}`;
  }
  document.getElementById('setting-ruler-file').value = rulerSelection;
  document.getElementById('setting-credit').value = project.credit_line || '';
  document.getElementById('setting-usage-terms').value = project.usage_terms || '';
  document.getElementById('setting-logo-path').value = project.logo_path || '';

  const bg = project.background_color || [0, 0, 0];
  const bgValue = (bg[0] > 128 && bg[1] > 128 && bg[2] > 128) ? 'white' : 'black';
  document.getElementById('setting-background').value = bgValue;
  document.querySelectorAll('.bg-swatch-setting').forEach(b =>
    b.classList.toggle('selected', b.dataset.bg === bgValue));
}

function showNewProjectPrompt() {
  const row = document.getElementById('setting-new-project-row');
  const input = document.getElementById('setting-new-project-name');
  row.classList.remove('hidden');
  input.value = '';
  input.focus();
}

function hideNewProjectPrompt() {
  document.getElementById('setting-new-project-row').classList.add('hidden');
  document.getElementById('setting-new-project-name').value = '';
}

async function createNewProject() {
  const name = document.getElementById('setting-new-project-name').value.trim();
  if (!name) {
    alert('Please enter a project name.');
    return;
  }
  const projects = await window.api.listProjects();
  if (projects.some(p => p.name === name)) {
    alert(`A project named "${name}" already exists.`);
    return;
  }
  const project = await window.api.newProject(name);
  await window.api.saveProject(project);
  hideNewProjectPrompt();
  await loadProjectList(name);
  setStatus(`Created project "${name}". Configure and Save Settings.`);
}

async function deleteSelectedProject() {
  const select = document.getElementById('setting-project-select');
  const name = select.value;
  if (!name) return;
  const project = await window.api.getProject(name);
  if (project && project.builtin) {
    alert(`"${name}" is a built-in project and cannot be deleted.`);
    return;
  }
  if (!confirm(`Delete project "${name}"?\n\nThis removes the saved configuration. Built-in defaults (if any) will reappear.`)) return;
  await window.api.deleteProject(name);
  await loadProjectList(null);
  setStatus(`Deleted project "${name}".`);
}

function closeSettings() {
  document.getElementById('settings-overlay').classList.add('hidden');
  hideNewProjectPrompt();
}

async function saveSettings() {
  // Save active project selection (stitcher exe is resolved to the bundled
  // binary automatically — no user config needed)
  const config = {
    activeProject: document.getElementById('setting-project-select').value,
  };
  await window.api.saveStitcherConfig(config);

  // Save project settings
  if (currentProjectName) {
    const bgValue = document.getElementById('setting-background').value;
    const project = {
      name: currentProjectName,
      photographer: document.getElementById('setting-photographer').value.trim(),
      institution: document.getElementById('setting-institution').value.trim(),
      measurements_file: document.getElementById('setting-measurements').value.trim(),
      fixed_ruler_position: 'bottom',
      ruler_position_locked: true,
      ruler_file: (() => {
        const v = document.getElementById('setting-ruler-file').value.trim();
        return v.startsWith('file:') ? v.slice(5) : (v.startsWith('set:') ? '' : v);
      })(),
      ruler_set: (() => {
        const v = document.getElementById('setting-ruler-file').value.trim();
        return v.startsWith('set:') ? v.slice(4) : '';
      })(),
      output_type: document.getElementById('setting-output-type').value,
      credit_line: document.getElementById('setting-credit').value.trim(),
      usage_terms: document.getElementById('setting-usage-terms').value.trim(),
      background_color: bgValue === 'white' ? [255, 255, 255] : [0, 0, 0],
      logo_path: document.getElementById('setting-logo-path').value.trim(),
      logo_enabled: !!document.getElementById('setting-logo-path').value.trim(),
    };

    // Merge with existing project to preserve fields we don't edit here
    const existing = await window.api.getProject(currentProjectName);
    if (existing) {
      Object.assign(existing, project);
      await window.api.saveProject(existing);
    } else {
      await window.api.saveProject(project);
    }
  }

  setStatus('Settings saved.');
  closeSettings();
}

// === Stitcher Processing ===
let isStitcherRunning = false;
let isConvertRawRunning = false;

async function onConvertRawClick(scope) {
  if (isStitcherRunning || isConvertRawRunning) {
    alert('Another stitcher / conversion run is already in progress.');
    return;
  }
  if (!state.rootFolder) {
    alert('Open a source folder first.');
    return;
  }

  // 'project' scope sends no explicit file list — the Python side walks the
  // root recursively. The other scopes send a specific list from state.
  if (scope === 'project') {
    const subfolders = state.subfolders || [];
    let total = 0;
    for (const sub of subfolders) {
      for (const img of (sub.images || [])) {
        if (RAW_EXTENSION_RE.test(img.name)) total++;
      }
    }
    if (total === 0) {
      alert('No RAW files found anywhere in this project.');
      return;
    }
    const ok = confirm(
      `Convert ${total} RAW file(s) across ${subfolders.length} subfolder(s) to 16-bit TIFF?\n\n` +
      `Output:    TIFFs saved next to each source file (same folder).\n` +
      `Existing TIFFs with the same name will be skipped.\n` +
      `Originals are NOT deleted.\n\n` +
      `This can take a while on large projects.`
    );
    if (!ok) return;
    await runConvertRaw(null); // null = let Python walk the root
    return;
  }

  const rawImages = (state.images || []).filter(i => RAW_EXTENSION_RE.test(i.name));
  const files = scope === 'selected'
    ? rawImages.filter(i => state.selectedImages.has(i.path))
    : rawImages;

  if (files.length === 0) {
    alert(scope === 'selected'
      ? 'No RAW files in the current selection.'
      : 'No RAW files in this folder.');
    return;
  }

  const totalSelected = scope === 'selected' ? state.selectedImages.size : files.length;
  const mixedNote = scope === 'selected' && totalSelected > files.length
    ? `\n${totalSelected - files.length} non-RAW file(s) in the selection will be ignored.`
    : '';

  const ok = confirm(
    `Convert ${files.length} RAW file(s) to 16-bit TIFF?\n\n` +
    `Output:    TIFFs saved next to each source file (same folder).\n` +
    `Existing TIFFs with the same name will be skipped.\n` +
    `Originals are NOT deleted.` + mixedNote
  );
  if (!ok) return;

  await runConvertRaw(files.map(f => f.path));
}

async function runConvertRaw(filePaths) {
  const verification = await window.api.verifyStitcherExe();
  if (!verification.valid) {
    alert(`Bundled stitcher not found: ${verification.reason}\n\nThis indicates a broken install — please reinstall eBL Tablet Studio.`);
    return;
  }

  isConvertRawRunning = true;
  updateConvertRawButtons();

  // Populate the Dashboard log in the background (for users who want full
  // detail) but stay on the Picker so the progress bar in the Conversion
  // tab is front-and-center.
  const statusEl = document.getElementById('stitcher-status');
  const dashProgressEl = document.getElementById('stitcher-progress');
  const dashEmpty = document.getElementById('dashboard-empty');
  const pickerStatus = document.getElementById('picker-convert-status');
  const pickerBar = document.getElementById('picker-convert-progress');
  const pickerLabel = document.getElementById('picker-convert-label');

  if (dashEmpty) dashEmpty.classList.add('hidden');
  if (statusEl) {
    statusEl.classList.remove('hidden');
    statusEl.replaceChildren();
    const startLine = filePaths
      ? `Converting ${filePaths.length} RAW file(s)...`
      : `Scanning project for RAW files and converting all of them...`;
    appendStitcherLine(statusEl, startLine);
  }
  if (dashProgressEl) {
    dashProgressEl.classList.remove('hidden');
    dashProgressEl.value = 0;
  }
  if (pickerStatus) pickerStatus.classList.remove('hidden');
  if (pickerBar) pickerBar.value = 0;
  if (pickerLabel) {
    pickerLabel.textContent = filePaths
      ? `Converting ${filePaths.length} RAW file(s)...`
      : 'Scanning project for RAW files...';
  }

  setStatus(`Converting RAW → TIFF...`);

  const result = await window.api.convertRawFiles(state.rootFolder, filePaths);

  isConvertRawRunning = false;
  updateConvertRawButtons();
  if (dashProgressEl) dashProgressEl.value = 100;
  if (pickerBar) pickerBar.value = 100;

  if (statusEl) {
    appendStitcherLine(statusEl, '');
    appendStitcherLine(statusEl, result.success
      ? '=== RAW CONVERSION DONE ==='
      : `=== RAW CONVERSION FINISHED (exit code ${result.exitCode}) ===`);
  }

  if (pickerLabel) {
    pickerLabel.textContent = result.success
      ? 'Done. See Results → Dashboard for per-file details.'
      : `Finished with errors (exit ${result.exitCode}). See Results → Dashboard.`;
  }

  setStatus(result.success
    ? 'RAW → TIFF conversion finished.'
    : `RAW → TIFF finished with errors (exit ${result.exitCode}).`);

  // Cancel any pending debounced auto-refresh so we don't rescan twice.
  if (_convertRefreshTimer) {
    clearTimeout(_convertRefreshTimer);
    _convertRefreshTimer = null;
  }

  // Final disk rescan to guarantee the tree + grid reflect every new TIFF,
  // including any file that landed after the last debounced auto-refresh.
  await refreshFromDisk();
}

// Helper: check if a tablet can be processed by the current user.
// Only tablets assigned to the current user OR unassigned are processable.
function isMyTablet(review) {
  if (!review?.assignedTo) return true;   // unassigned = anyone can process
  return review.assignedTo === currentUserName;
}

function updateProcessButton() {
  const btn = document.getElementById('btn-process');
  const myReadyCount = Object.values(resultsState.reviewStatus)
    .filter(r => r.status === 'updated' && isMyTablet(r)).length;
  btn.disabled = myReadyCount === 0 || isStitcherRunning || !state.rootFolder;
  btn.title = myReadyCount > 0
    ? `Process ${myReadyCount} of your ready (green) folder(s)`
    : 'Mark your folders as ready (green) in the tree first';
}

async function onProcessReady() {
  if (isStitcherRunning) {
    alert('Stitcher is already running.');
    return;
  }

  const ready = Object.entries(resultsState.reviewStatus)
    .filter(([, v]) => v.status === 'updated' && isMyTablet(v))
    .map(([name]) => name);

  if (ready.length === 0) {
    alert('No folders assigned to you are marked as ready (green).\n\nAssign tablets to yourself first, then mark them as ready.');
    return;
  }

  const ok = confirm(`Process ${ready.length} ready folder(s)?\n\n${ready.join('\n')}`);
  if (!ok) return;

  await runStitcher(ready);
}

async function reprocessAll() {
  if (isStitcherRunning) {
    alert('Stitcher is already running.');
    return;
  }

  if (state.subfolders.length === 0) {
    alert('No subfolders loaded.');
    return;
  }

  const ok = confirm(`Reprocess ALL ${state.subfolders.length} tablet(s)?\nThis may take a long time.`);
  if (!ok) return;

  await runStitcher(null);
}

async function runStitcher(tablets) {
  // Bundled stitcher binary is always present; just sanity-check before running.
  const verification = await window.api.verifyStitcherExe();
  if (!verification.valid) {
    alert(`Bundled stitcher not found: ${verification.reason}\n\nThis indicates a broken install — please reinstall eBL Tablet Studio.`);
    return;
  }

  // In renamer mode, process from the Selected folder
  const exportBase = customExportFolder || (state.rootFolder + '/_Selected');
  const rootFolder = appMode === 'renamer' ? exportBase : state.rootFolder;

  isStitcherRunning = true;
  document.getElementById('btn-reprocess-all').disabled = true;

  // Figure out which variants this run will produce so the 'sent' badge can
  // be scoped correctly. Falls back to 'digital' if the project/output_type
  // can't be resolved.
  try {
    const config = await window.api.getStitcherConfig();
    const project = config?.activeProject ? await window.api.getProject(config.activeProject) : null;
    const outputType = project?.output_type || 'digital';
    if (outputType === 'print') _currentRunVariants = ['print'];
    else if (outputType === 'both') _currentRunVariants = ['digital', 'print'];
    else _currentRunVariants = ['digital'];
  } catch {
    _currentRunVariants = ['digital'];
  }

  document.querySelector('.right-tab[data-tab="results"]')?.click();

  setResultView('dashboard');
  const statusEl = document.getElementById('stitcher-status');
  const progressEl = document.getElementById('stitcher-progress');
  const dashEmpty = document.getElementById('dashboard-empty');
  if (dashEmpty) dashEmpty.classList.add('hidden');
  statusEl.classList.remove('hidden');
  statusEl.replaceChildren();
  appendStitcherLine(statusEl, 'Starting stitcher...');
  if (progressEl) {
    progressEl.classList.remove('hidden');
    progressEl.value = 0;
  }

  setStatus('Stitcher running...');

  // Track which tablets were sent
  const sentTablets = tablets || (appMode === 'renamer'
    ? selectedTreeFolders.map(f => f.name)
    : state.subfolders.map(s => s.name));

  // Clean cached _object.tif and _ruler.tif files so the stitcher
  // re-extracts from the (possibly edited) source images
  appendStitcherLine(statusEl, 'Cleaning cached files...');
  const cleanedCount = await window.api.cleanTabletCache(rootFolder, tablets);
  if (cleanedCount > 0) {
    appendStitcherLine(statusEl, `Removed ${cleanedCount} cached file(s).`);
  }

  const result = await window.api.processTablets(rootFolder, tablets);

  isStitcherRunning = false;
  document.getElementById('btn-reprocess-all').disabled = false;

  if (progressEl) {
    progressEl.value = 100;
  }

  // Mark each sent tablet as 'sent' (yellow) only on the variants this run
  // actually produced — stale opposite-variant files keep their old status.
  for (const name of sentTablets) {
    for (const variant of _currentRunVariants) {
      markVariantSent(name, variant);
    }
  }
  await window.api.saveReviewStatus(getResultsRoot(), resultsState.reviewStatus);

  if (result.success) {
    setStatus('Stitcher finished. Review the results.');
    appendStitcherLine(statusEl, '');
    appendStitcherLine(statusEl, '=== DONE ===');
  } else {
    setStatus(`Stitcher finished with errors. Review the results.`);
    appendStitcherLine(statusEl, '');
    appendStitcherLine(statusEl, `=== FINISHED (exit code ${result.exitCode}) ===`);
  }

  await loadResults();
  updateTreeStatusIcons();
}

const TABLET_BANNER_RE = /^Processing Subfolder \d+\/\d+: .+$/;
const MEASUREMENT_LINE_RE = /measurement|px\/cm|Measurements saved/i;
const TABLET_FINISHED_RE = /^Finished processing and stitching for tablet:\s*(.+?)\s*$/;

// Which variants (digital / print) the most recent stitcher run produced.
// Populated from the active project's output_type when runStitcher starts, and
// used to scope the yellow 'sent' badge: only variants that were actually
// regenerated in this run get marked. Stale variants from earlier runs stay
// untouched (no "sent" badge appears on them).
let _currentRunVariants = ['digital'];

function getEffectiveReview(review, variant = 'digital') {
  if (!review) return {};
  const varReview = review.variants?.[variant];
  if (varReview?.status) {
    return { ...review, ...varReview };
  }
  return review;
}

function markVariantSent(tabletName, variant) {
  const entry = resultsState.reviewStatus[tabletName] || {};
  // Strip any legacy top-level 'sent' so it doesn't shadow other variants —
  // that marker predates the per-variant schema and should only apply to
  // whatever is regenerated now. Manual statuses (updated/revision/finished)
  // stay at top-level because those apply to the tablet as a whole.
  const base = { ...entry };
  if (base.status === 'sent') delete base.status;
  const variants = { ...(base.variants || {}) };
  variants[variant] = {
    ...(variants[variant] || {}),
    status: 'sent',
    reviewedAt: new Date().toISOString(),
  };
  resultsState.reviewStatus[tabletName] = { ...base, variants };
}

let _incrementalResultsTimer = null;
const _incrementalSentNames = new Set();

function scheduleIncrementalResultsRefresh(tabletName) {
  if (tabletName) _incrementalSentNames.add(tabletName);
  // Debounce so back-to-back finishes (e.g. the tail of one tablet + the
  // banner of the next) only trigger one rescan. 1.5s is short enough that
  // users see new thumbnails quickly and long enough to absorb bursts.
  if (_incrementalResultsTimer) clearTimeout(_incrementalResultsTimer);
  _incrementalResultsTimer = setTimeout(async () => {
    _incrementalResultsTimer = null;
    try {
      const names = Array.from(_incrementalSentNames);
      _incrementalSentNames.clear();
      // Apply 'sent' status to freshly finished tablets (per variant) before
      // the rescan so the yellow badge appears on the new thumbnails
      // immediately. Only variants produced by the current run are marked.
      if (names.length > 0) {
        for (const name of names) {
          for (const variant of _currentRunVariants) {
            markVariantSent(name, variant);
          }
        }
        await window.api.saveReviewStatus(getResultsRoot(), resultsState.reviewStatus);
      }
      await loadResults();
    } catch (err) {
      console.error('Incremental loadResults failed:', err);
    }
  }, 1500);
}

function appendStitcherLine(statusEl, text) {
  const div = document.createElement('div');
  if (TABLET_BANNER_RE.test(text)) {
    div.className = 'tablet-banner';
  } else if (MEASUREMENT_LINE_RE.test(text)) {
    div.className = 'log-line measurement-line';
  } else {
    div.className = 'log-line';
  }
  div.textContent = text;
  statusEl.appendChild(div);
  statusEl.scrollTop = statusEl.scrollHeight;

  const finishMatch = text.match(TABLET_FINISHED_RE);
  if (finishMatch) {
    scheduleIncrementalResultsRefresh(finishMatch[1]);
  }
}

const CONVERT_RAW_LINE_RE = /^\[(\d+)\/(\d+)\]\s+(Converting|Skipping)\s+(.+?)(?:\s+—|\s+→|$)/;

let _convertRefreshTimer = null;
function scheduleConvertRefresh() {
  // Debounced rescan while a conversion run is active. The progress stream
  // fires one "Converting …" line per file; chaining a refresh to each
  // would thrash disk I/O and flicker the grid. A 2s debounce lets a burst
  // of file completions coalesce into a single rescan.
  if (_convertRefreshTimer) clearTimeout(_convertRefreshTimer);
  _convertRefreshTimer = setTimeout(() => {
    _convertRefreshTimer = null;
    if (isConvertRawRunning) {
      refreshFromDisk().catch(err => console.error('Auto-refresh failed:', err));
    }
  }, 2000);
}

function handleStitcherProgress(event) {
  const statusEl = document.getElementById('stitcher-status');
  if (!statusEl) return;

  if (event.type === 'progress') {
    const pct = event.value;
    setStatus(isConvertRawRunning ? `Converting RAW: ${pct}%` : `Stitcher: ${pct}%`);
    const progressEl = document.getElementById('stitcher-progress');
    if (progressEl) progressEl.value = pct;
    const pickerBar = document.getElementById('picker-convert-progress');
    if (pickerBar && isConvertRawRunning) pickerBar.value = pct;
  } else if (event.type === 'log' || event.type === 'stderr') {
    appendStitcherLine(statusEl, event.message);
    // While a RAW conversion is running, mirror the "[n/m] Converting foo.cr2"
    // lines into the Conversion tab's status label AND schedule a debounced
    // rescan so new TIFFs appear in the grid without the user clicking refresh.
    if (isConvertRawRunning) {
      const pickerLabel = document.getElementById('picker-convert-label');
      const m = event.message.match(CONVERT_RAW_LINE_RE);
      if (m && pickerLabel) {
        const verb = m[3] === 'Skipping' ? 'Skipped' : 'Converting';
        pickerLabel.textContent = `[${m[1]}/${m[2]}] ${verb} ${m[4]}`;
      }
      if (m) scheduleConvertRefresh();
    }
  } else if (event.type === 'error') {
    appendStitcherLine(statusEl, `ERROR: ${event.message}`);
  }
}

// =====================================================================
// Picker Mode
// =====================================================================

function switchMode(mode) {
  if (mode === appMode) return;
  appMode = mode;

  document.getElementById('btn-mode-renamer').classList.toggle('active', mode === 'renamer');
  document.getElementById('btn-mode-picker').classList.toggle('active', mode === 'picker');
  document.body.classList.toggle('picker-mode', mode === 'picker');

  // Reset selection / thumbnails / panels on every mode switch
  // Close the full-image viewer if it was open (so we don't keep showing an
  // image that belongs to the other mode's folder)
  if (isViewerOpen()) exitViewerMode();

  // Also deactivate any active tool (like Segment) to avoid stale state
  if (previewTool.active) setActiveTool(previewTool.active);

  state.currentIndex = -1;
  selectedTreeIndex = -1;
  state.images = [];
  state.selectedImage = null;
  state.selectedImages.clear();
  state.assignments = {};
  state.reverseAssignments = {};
  dom.thumbGrid.innerHTML = '';
  dom.subfolderInfo.textContent = '';

  // Reset tree search
  const searchInput = document.getElementById('tree-search');
  if (searchInput) searchInput.value = '';

  // Always return to the Structure tab on mode switch
  document.querySelectorAll('.right-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === 'structure');
  });
  document.querySelectorAll('.tab-content').forEach(c => {
    c.classList.toggle('active', c.id === 'tab-structure');
  });
  activeTab = 'structure';

  // Refresh the structure diagram so stale slot highlights/filenames clear
  updateStructureDiagram();

  // Rebuild tree for the new mode
  buildTreeView();
  updateButtons();
  if (mode === 'renamer') {
    loadResults();
    startStatusRefresh();
  } else {
    stopStatusRefresh();
  }
}

let selectedTreeFolders = []; // cached selected folder scan results
let selectedTreeLooseImages = []; // loose image files at the root of _Selected/
let selectedTreeIndex = -1; // current index in selected tree

// Sentinel for the pseudo-entry that represents loose-at-root files in either
// picker or renamer tree. Negative index distinguishes it from real folders.
const LOOSE_TREE_INDEX = -42;

async function buildSelectedTree() {
  const treeList = document.getElementById('tree-list');
  treeList.innerHTML = '';
  document.getElementById('tree-header').textContent = 'Selected';

  const exportBase = customExportFolder || (state.rootFolder ? state.rootFolder + '/_Selected' : null);
  if (!exportBase) {
    treeList.innerHTML = '<div class="tree-empty">No export folder set</div>';
    selectedTreeFolders = [];
    selectedTreeLooseImages = [];
    return;
  }

  // Backwards-compat: older scanSelectedFolder returned a bare array; new
  // shape is { subfolders, looseImages }. Normalize so both work.
  const scan = await window.api.scanSelectedFolder(exportBase);
  const folders = Array.isArray(scan) ? scan : (scan.subfolders || []);
  const loose = Array.isArray(scan) ? [] : (scan.looseImages || []);
  selectedTreeFolders = folders;
  selectedTreeLooseImages = loose;

  if (folders.length === 0 && loose.length === 0) {
    treeList.innerHTML = '<div class="tree-empty">No exported tablets yet</div>';
    return;
  }

  if (loose.length > 0) {
    const item = document.createElement('div');
    item.className = 'tree-item tree-loose-entry';
    item.dataset.selectedIndex = String(LOOSE_TREE_INDEX);
    item.innerHTML = `<span class="tree-name">(Loose files)</span><span class="tree-count">(${loose.length})</span>`;
    item.title = 'Image files at the root of the Selected folder, not in any tablet subfolder. Click to browse and group them.';
    item.addEventListener('click', () => {
      loadLooseSelectedImages();
    });
    treeList.appendChild(item);
  }

  for (let i = 0; i < folders.length; i++) {
    const folder = folders[i];
    const item = document.createElement('div');
    item.className = 'tree-item tree-selected-item';
    item.dataset.selectedIndex = i;
    item.innerHTML = `${folder.name}<span class="tree-count">(${folder.imageCount})</span>`;
    item.addEventListener('click', () => {
      loadSelectedFolder(i);
    });
    treeList.appendChild(item);
  }

  updateTreeStatusIcons();
}

async function loadLoosePickerImages() {
  // Picker-side equivalent: expose the root-level loose images in the grid so
  // the user can select / pick / organize them without needing per-tablet
  // subfolders to exist first.
  if (isViewerOpen()) exitViewerMode();
  state.currentIndex = -1;
  state.images = (state.looseImages || []).map(f => ({
    path: f.path, name: f.name, ext: f.ext,
    detectedView: null,
  }));
  state.selectedImage = null;
  state.selectedImages.clear();
  state.lastClickedIndex = -1;
  state.assignments = {};
  state.reverseAssignments = {};

  dom.subfolderInfo.textContent = `(Loose files in ${state.rootFolder})  (${state.images.length})`;
  dom.btnPrev.disabled = true;
  dom.btnNext.disabled = true;
  dom.btnSkip.disabled = true;

  document.querySelectorAll('.tree-item').forEach(el => {
    el.classList.toggle('active', el.dataset.index === '-1');
  });

  dom.thumbGrid.innerHTML = '';
  for (const img of state.images) {
    dom.thumbGrid.appendChild(createThumbCard(img));
  }
  for (const img of state.images) {
    loadThumbnail(img.path, getCardForImage(img.path));
  }
  updateSelectionUI();
  updatePickerFolderStats();
  setStatus(`${state.images.length} loose file(s). Select some, then use Settings → "Group selected into folder…" or "Organize by filename (auto)".`);
}

async function loadLooseSelectedImages() {
  // Show loose files from the renamer's _Selected root in the thumbnail grid
  // so the user can browse + select them, then group into a named folder.
  if (isViewerOpen()) exitViewerMode();
  const exportBase = customExportFolder || (state.rootFolder + '/_Selected');
  state.images = selectedTreeLooseImages.map(f => ({
    path: f.path, name: f.name, ext: f.ext,
    detectedView: null,
  }));
  state.selectedImage = null;
  state.selectedImages.clear();
  state.lastClickedIndex = -1;
  state.assignments = {};
  state.reverseAssignments = {};
  selectedTreeIndex = LOOSE_TREE_INDEX;

  dom.subfolderInfo.textContent = `(Loose files in ${exportBase})  (${state.images.length})`;
  dom.btnPrev.disabled = true;
  dom.btnNext.disabled = true;
  dom.btnSkip.disabled = true;

  document.querySelectorAll('.tree-item').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.selectedIndex) === LOOSE_TREE_INDEX);
  });

  dom.thumbGrid.innerHTML = '';
  for (const img of state.images) {
    dom.thumbGrid.appendChild(createThumbCard(img));
  }
  for (const img of state.images) {
    loadThumbnail(img.path, getCardForImage(img.path));
  }
  setStatus(`${state.images.length} loose file(s). Select some, then use "Group selected into folder…" in the Picker's Settings tab or the renamer's toolbar.`);
}

async function loadSelectedFolder(index) {
  const folder = selectedTreeFolders[index];
  if (!folder) return;
  // Same rationale as loadCurrentSubfolder: drop the viewer when folder
  // changes so we land on the new folder's grid, not a stale single image.
  if (isViewerOpen()) exitViewerMode();
  selectedTreeIndex = index;

  // Highlight active item
  document.querySelectorAll('.tree-selected-item').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.selectedIndex) === index);
  });

  // Scan the export base to get proper image data for this subfolder
  const exportBase = customExportFolder || (state.rootFolder + '/_Selected');
  const result = await window.api.scanFolder(exportBase);
  const sub = result.subfolders.find(s => s.name === folder.name);
  if (!sub) {
    setStatus(`Could not load ${folder.name}`);
    return;
  }

  // Load into the main panel
  state.images = sub.images;
  state.selectedImage = null;
  state.selectedImages.clear();
  state.lastClickedIndex = -1;
  state.assignments = {};
  state.reverseAssignments = {};

  dom.subfolderInfo.textContent = `${folder.name}  (${index + 1} / ${selectedTreeFolders.length})`;
  dom.btnPrev.disabled = index === 0;
  dom.btnNext.disabled = index >= selectedTreeFolders.length - 1;
  dom.btnSkip.disabled = index >= selectedTreeFolders.length - 1;

  // Auto-detect existing assignments from filenames (to show in structure diagram)
  for (const img of state.images) {
    if (img.detectedView && !state.reverseAssignments[img.detectedView]) {
      state.assignments[img.path] = img.detectedView;
      state.reverseAssignments[img.detectedView] = img.path;
    }
  }

  // Render thumbnails
  dom.thumbGrid.innerHTML = '';
  setStatus(`Loading ${state.images.length} thumbnails...`);

  for (const img of state.images) {
    const card = createThumbCard(img);
    dom.thumbGrid.appendChild(card);
    loadThumbnail(img.path, card);
  }

  if (state.images.length > 0) {
    selectImage(state.images[0].path);
  }

  updateStructureDiagram();
  updateButtons();
  updateStatusCount();
}

const RAW_EXTENSION_RE = /\.(cr2|cr3|nef|arw|raf|rw2)$/i;

function setPickerTab(name) {
  if (!name) return;
  document.querySelectorAll('.picker-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.pickerTab === name);
  });
  document.querySelectorAll('.picker-tab-panel').forEach(panel => {
    panel.classList.toggle('active', panel.dataset.pickerPanel === name);
  });
}

function updatePickerFolderStats() {
  const nameEl = document.getElementById('picker-stat-name');
  const totalEl = document.getElementById('picker-stat-total');
  const rawEl = document.getElementById('picker-stat-raw');
  const pickedEl = document.getElementById('picker-stat-picked');
  const clearBtn = document.getElementById('btn-picker-clear-picks');
  const revealBtn = document.getElementById('btn-picker-reveal');
  const orgBtn = document.getElementById('btn-picker-organize');
  if (!nameEl) return;

  // Organize button reflects loose photos at the root — doesn't depend on
  // a specific subfolder being open.
  const looseCount = (state.looseImages || []).length;
  if (orgBtn) {
    orgBtn.textContent = `Organize by filename (auto) — ${looseCount} loose`;
    orgBtn.disabled = looseCount === 0;
  }

  // Group-selected button: enabled whenever the grid has at least one
  // selected file AND we're currently showing the loose images (otherwise
  // grouping "selected" from inside a real subfolder doesn't make sense).
  const groupBtn = document.getElementById('btn-picker-group-selected');
  if (groupBtn) {
    const viewingLoose = state.currentIndex === -1 && (state.looseImages || []).length > 0;
    const selCount = state.selectedImages ? state.selectedImages.size : 0;
    groupBtn.textContent = `Group selected into folder… (${selCount})`;
    groupBtn.disabled = !viewingLoose || selCount === 0;
  }

  const sub = state.subfolders[state.currentIndex];
  if (!sub) {
    // If we're browsing the "(Loose files)" pseudo-entry, show its stats;
    // otherwise fall back to the blank state.
    const viewingLoose = state.currentIndex === -1 && (state.images || []).length > 0
      && (state.looseImages || []).length > 0;
    if (viewingLoose) {
      const images = state.images || [];
      const rawCount = images.filter(i => RAW_EXTENSION_RE.test(i.name)).length;
      nameEl.textContent = '(Loose files)';
      totalEl.textContent = String(images.length);
      rawEl.textContent = String(rawCount);
      pickedEl.textContent = String(Object.keys(state.assignments || {}).length);
      clearBtn.disabled = Object.keys(state.assignments || {}).length === 0;
      revealBtn.disabled = !state.rootFolder;
    } else {
      nameEl.textContent = '—';
      totalEl.textContent = '0';
      rawEl.textContent = '0';
      pickedEl.textContent = '0';
      clearBtn.disabled = true;
      revealBtn.disabled = true;
    }
    return;
  }

  const images = state.images || [];
  const rawCount = images.filter(i => RAW_EXTENSION_RE.test(i.name)).length;
  const pickedCount = Object.keys(state.assignments || {}).length;

  nameEl.textContent = sub.name;
  totalEl.textContent = String(images.length);
  rawEl.textContent = String(rawCount);
  pickedEl.textContent = String(pickedCount);
  clearBtn.disabled = pickedCount === 0;
  revealBtn.disabled = !sub.path;
}

async function onPickerClearPicks() {
  if (!state.subfolders[state.currentIndex]) return;
  const pickedCount = Object.keys(state.assignments || {}).length;
  if (pickedCount === 0) return;
  const ok = confirm(`Clear all ${pickedCount} pick(s) in this folder? The image files are not touched — this only resets the assignment list.`);
  if (!ok) return;
  state.assignments = {};
  updatePickerList();
  updatePickerFolderStats();
  setStatus('Picks cleared for this folder.');
}

async function onPickerRevealFolder() {
  const sub = state.subfolders[state.currentIndex];
  if (!sub || !sub.path) return;
  await window.api.revealInExplorer(sub.path);
}

function showGroupSelectedPrompt() {
  const row = document.getElementById('picker-group-name-row');
  const input = document.getElementById('picker-group-name-input');
  if (!state.selectedImages || state.selectedImages.size === 0) {
    alert('Select one or more loose files in the grid first.');
    return;
  }
  row.classList.remove('hidden');
  input.value = '';
  input.focus();
}

function hideGroupSelectedPrompt() {
  document.getElementById('picker-group-name-row').classList.add('hidden');
  document.getElementById('picker-group-name-input').value = '';
}

async function confirmGroupSelected() {
  const input = document.getElementById('picker-group-name-input');
  const folderName = input.value.trim();
  if (!folderName) {
    alert('Enter a folder name.');
    return;
  }
  const selectedPaths = Array.from(state.selectedImages || []);
  if (selectedPaths.length === 0) {
    alert('Select one or more files first.');
    return;
  }
  setStatus(`Moving ${selectedPaths.length} file(s) into "${folderName}/"...`);
  try {
    const result = await window.api.moveFilesToFolder(selectedPaths, folderName);
    if (result.error) {
      alert(`Could not group files: ${result.error}`);
      return;
    }
    const parts = [`Moved ${result.moved.length} into "${folderName}/"`];
    if (result.collisions.length > 0) parts.push(`${result.collisions.length} skipped (name conflict)`);
    setStatus(parts.join('; ') + '.');
    hideGroupSelectedPrompt();
    await refreshFromDisk();
  } catch (err) {
    console.error('Group failed:', err);
    alert(`Could not group files: ${err.message}`);
  }
}

/**
 * Organizer entry point from the Settings tab. Uses the current state's
 * loose-image count; opens the same confirm dialog as the auto-prompt.
 */
async function onPickerOrganizeClick() {
  if (!state.rootFolder) return;
  const count = (state.looseImages || []).length;
  if (count === 0) {
    setStatus('No loose photos to organize in this folder.');
    return;
  }
  const accepted = await promptOrganizeLoosePhotos(state.rootFolder, count);
  if (accepted) {
    await openFolder(state.rootFolder);
  }
}

/**
 * Show the confirm dialog + run the organizer, reporting per-file stats.
 * Returns true if files were actually moved (so the caller knows whether to
 * re-scan), false if the user canceled or nothing happened.
 */
async function promptOrganizeLoosePhotos(rootFolder, count) {
  const ok = confirm(
    `This folder contains ${count} photo file(s) not grouped into tablet subfolders.\n\n` +
    `Organize them automatically by filename?\n` +
    `  Files matching "<TabletID>_<view>.<ext>" (e.g. Si.32_01.jpg) move into\n` +
    `  "<TabletID>/" subfolders.\n\n` +
    `Unmatched files stay at the root. Existing files in target subfolders\n` +
    `are not overwritten.`
  );
  if (!ok) return false;

  setStatus(`Organizing ${count} photo(s)...`);
  try {
    const result = await window.api.organizeLoosePhotos(rootFolder);
    const parts = [`Moved ${result.moved.length}`];
    if (result.skipped.length > 0) parts.push(`skipped ${result.skipped.length} (didn't match pattern)`);
    if (result.collisions.length > 0) parts.push(`skipped ${result.collisions.length} (collision)`);
    setStatus(parts.join('; ') + '.');
    return result.moved.length > 0;
  } catch (err) {
    console.error('Organize failed:', err);
    alert(`Could not organize photos: ${err.message}`);
    return false;
  }
}

/**
 * Re-scan the root from disk and rebuild both the tree and the currently-
 * opened subfolder. Picks up new files created by the RAW converter and
 * drops files that were deleted externally.
 *
 * Works in both picker and renamer modes — each mode uses its own scanner
 * (scanFolder for the source tree, scanSelectedFolder for the export tree).
 */
async function refreshFromDisk() {
  if (!state.rootFolder) {
    setStatus('Open a folder first.');
    return;
  }
  const btn = document.getElementById('btn-tree-refresh');
  if (btn) btn.disabled = true;
  try {
    if (appMode === 'renamer') {
      await buildSelectedTree();
      if (selectedTreeIndex >= 0 && selectedTreeFolders[selectedTreeIndex]) {
        await loadSelectedFolder(selectedTreeIndex);
      }
    } else {
      const result = await window.api.scanFolder(state.rootFolder);
      state.subfolders = result.subfolders;
      state.looseImages = result.looseImages || [];
      buildTreeView();
      if (state.subfolders[state.currentIndex]) {
        await loadCurrentSubfolder();
      } else {
        // Refresh Settings-tab stats so the Organize button reflects any
        // change in loose-photo count (e.g. after a RAW conversion wrote
        // TIFFs next to the originals at the root).
        updatePickerFolderStats();
      }
    }
    setStatus('Folder rescanned from disk.');
  } catch (err) {
    console.error('Refresh failed:', err);
    setStatus(`Refresh failed: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function updateConvertRawButtons() {
  const selBtn = document.getElementById('btn-convert-raw-selected');
  const allBtn = document.getElementById('btn-convert-raw-all');
  const projBtn = document.getElementById('btn-convert-raw-project');
  if (!selBtn || !allBtn || !projBtn) return;

  const images = (state.images || []).filter(i => RAW_EXTENSION_RE.test(i.name));
  const selectedRaw = images.filter(i => state.selectedImages.has(i.path));
  const allCount = images.length;
  const selCount = selectedRaw.length;

  // Project-wide count: sum CR2s across every scanned subfolder.
  let projectCount = 0;
  for (const sub of (state.subfolders || [])) {
    if (!sub.images) continue;
    for (const img of sub.images) {
      if (RAW_EXTENSION_RE.test(img.name)) projectCount++;
    }
  }

  selBtn.textContent = `Convert selected (${selCount})`;
  allBtn.textContent = `Convert all in folder (${allCount})`;
  projBtn.textContent = `Convert entire project (${projectCount})`;

  const busy = isStitcherRunning || isConvertRawRunning;
  selBtn.disabled = busy || selCount === 0;
  allBtn.disabled = busy || allCount === 0;
  projBtn.disabled = busy || projectCount === 0;
}

function updatePickerList() {
  if (appMode !== 'picker') return;

  const listEl = document.getElementById('picker-list');
  const countEl = document.getElementById('picker-count');
  const exportBtn = document.getElementById('btn-export-selected');
  if (!listEl) return;

  updateConvertRawButtons();

  listEl.innerHTML = '';
  const picks = Object.entries(state.assignments)
    .sort(([, a], [, b]) => a.localeCompare(b));

  countEl.textContent = `${picks.length} picked`;
  exportBtn.disabled = picks.length === 0;

  updatePickerFolderStats();

  for (const [imgPath, code] of picks) {
    const img = state.images.find(i => i.path === imgPath);
    if (!img) continue;

    const item = document.createElement('div');
    item.className = 'pick-item';

    const codeSpan = document.createElement('span');
    codeSpan.className = 'pick-code';
    codeSpan.textContent = code === 'pick' ? '\u2713' : code;
    item.appendChild(codeSpan);

    const viewSpan = document.createElement('span');
    viewSpan.className = 'pick-name';
    viewSpan.textContent = code === 'pick' ? img.name : `${VIEW_CODES[code] || code} — ${img.name}`;
    item.appendChild(viewSpan);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'pick-remove';
    removeBtn.textContent = '\u00D7';
    removeBtn.title = 'Remove pick';
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Unassign this pick
      delete state.reverseAssignments[code];
      delete state.assignments[imgPath];
      updateCardBadge(imgPath);
      updatePickerList();
      updateStatusCount();
      savePicksDebounced();
    });
    item.appendChild(removeBtn);

    item.addEventListener('click', () => {
      selectImage(imgPath);
    });

    listEl.appendChild(item);
  }
}

let picksDebounceTimer = null;
function savePicksDebounced() {
  if (picksDebounceTimer) clearTimeout(picksDebounceTimer);
  picksDebounceTimer = setTimeout(async () => {
    const sub = state.subfolders[state.currentIndex];
    if (!sub) return;
    // Convert assignments (imagePath -> viewCode) to (filename -> viewCode)
    const picks = {};
    for (const [imgPath, viewCode] of Object.entries(state.assignments)) {
      const img = state.images.find(i => i.path === imgPath);
      if (img) picks[img.name] = viewCode;
    }
    await window.api.savePicks(sub.path, picks);
  }, 500);
}

function updateExportFolderDisplay() {
  const el = document.getElementById('picker-folder-path');
  if (customExportFolder) {
    // Show just the folder name, not full path
    const parts = customExportFolder.replace(/\\/g, '/').split('/');
    el.textContent = parts[parts.length - 1] || customExportFolder;
    el.title = customExportFolder;
  } else {
    el.textContent = '_Selected';
    el.title = 'Default: _Selected folder in root';
  }
}

async function onExportSelected() {
  const count = Object.keys(state.assignments).length;
  if (count === 0) {
    alert('No images have been picked.');
    return;
  }

  // Determine export folder
  const exportBase = customExportFolder || (state.rootFolder ? state.rootFolder + '/_Selected' : null);
  if (!exportBase) {
    alert('No export folder set. Use the browse button to select one.');
    return;
  }

  // When viewing the "(Loose files)" pseudo-entry there's no real subfolder
  // to read the tablet name from. Prompt the user for one instead. This keeps
  // the loose-files → export flow unblocked for photos whose filenames don't
  // already carry a tablet ID.
  let tabletName;
  const sub = state.subfolders[state.currentIndex];
  if (sub) {
    tabletName = sub.name.replace(/(\w+)\s+(\d+)/g, '$1.$2');
  } else {
    const entered = await promptForText(
      'Tablet name',
      'Will create a subfolder by this name under the export folder.',
      'e.g. Si.32'
    );
    if (entered === null) return; // user canceled
    tabletName = entered;
    if (/[\\/:*?"<>|]/.test(tabletName) || tabletName === '.' || tabletName === '..') {
      alert('Invalid tablet name.');
      return;
    }
  }

  const lines = Object.entries(state.assignments)
    .sort(([, a], [, b]) => a.localeCompare(b))
    .map(([imgPath, code]) => {
      const img = state.images.find(i => i.path === imgPath);
      if (code === 'pick') {
        return `  ${img?.name || '?'}  (unnamed pick)`;
      }
      const ext = img ? img.ext : '.jpg';
      return `  ${img?.name || '?'}  \u2192  ${tabletName}_${code}${ext}`;
    });

  const folderLabel = customExportFolder
    ? customExportFolder.replace(/\\/g, '/').split('/').pop()
    : '_Selected';

  const ok = confirm(
    `Export ${count} picked image(s) to ${folderLabel}/${tabletName}/ ?\n\n${lines.join('\n')}`
  );
  if (!ok) return;

  setStatus('Exporting selected images...');

  const result = await window.api.exportSelected(
    state.rootFolder,
    tabletName,
    state.assignments,
    customExportFolder,
  );

  if (result.success) {
    setStatus(`Exported ${result.count} image(s) to ${folderLabel}/${tabletName}/`);
    // Rebuild according to current mode — buildSelectedTree would overwrite
    // the picker's source tree with the renamer's "Selected" view otherwise.
    buildTreeView();
  } else {
    setStatus(`Export failed: ${result.error}`);
  }
}

// === User Identity (collaboration) ===
// On startup, load or prompt for a display name. Used for tablet assignments.

/**
 * Modal text prompt (Electron disables window.prompt, so this is our
 * stand-in). Returns the entered string, or null if the user cancels.
 */
function promptForText(title, message, placeholder = '', defaultValue = '') {
  return new Promise((resolve) => {
    const overlay = document.getElementById('text-prompt-overlay');
    const titleEl = document.getElementById('text-prompt-title');
    const messageEl = document.getElementById('text-prompt-message');
    const input = document.getElementById('text-prompt-input');
    const okBtn = document.getElementById('text-prompt-ok');
    const cancelBtn = document.getElementById('text-prompt-cancel');

    titleEl.textContent = title;
    messageEl.textContent = message || '';
    messageEl.style.display = message ? '' : 'none';
    input.placeholder = placeholder;
    input.value = defaultValue;
    input.disabled = false;
    input.readOnly = false;
    overlay.classList.remove('hidden');
    // requestAnimationFrame so the layout settles before focusing — otherwise
    // Electron sometimes drops the .focus() call silently when the element
    // was just un-hidden in the same frame and the user can't type.
    requestAnimationFrame(() => {
      input.focus();
      input.select();
    });

    const cleanup = () => {
      overlay.classList.add('hidden');
      okBtn.removeEventListener('click', submit);
      cancelBtn.removeEventListener('click', cancel);
      input.removeEventListener('keydown', keyHandler);
      overlay.removeEventListener('keydown', trapKeys, true);
      overlay.removeEventListener('click', outsideClick);
    };

    function submit() {
      const val = input.value.trim();
      cleanup();
      resolve(val || null);
    }
    function cancel() {
      cleanup();
      resolve(null);
    }
    function keyHandler(e) {
      if (e.key === 'Enter') { e.preventDefault(); submit(); }
      else if (e.key === 'Escape') { e.preventDefault(); cancel(); }
    }
    // Capture-phase handler on the overlay so global keyboard shortcuts
    // (Ctrl+S, Ctrl+E in the main onKeyDown) don't fire while the modal is
    // open — the user's typing was falling through to them and triggering
    // the full export flow mid-input.
    function trapKeys(e) {
      e.stopPropagation();
    }
    function outsideClick(e) {
      if (e.target === overlay) cancel();
    }

    okBtn.addEventListener('click', submit);
    cancelBtn.addEventListener('click', cancel);
    input.addEventListener('keydown', keyHandler);
    overlay.addEventListener('keydown', trapKeys, true);
    overlay.addEventListener('click', outsideClick);
  });
}

function showUserNameDialog(prefill) {
  return new Promise((resolve) => {
    const overlay = document.getElementById('user-name-overlay');
    const input = document.getElementById('user-name-input');
    const okBtn = document.getElementById('user-name-ok');
    input.value = prefill || '';
    overlay.classList.remove('hidden');
    input.focus();

    function submit() {
      const val = input.value.trim();
      overlay.classList.add('hidden');
      okBtn.removeEventListener('click', submit);
      input.removeEventListener('keydown', onKey);
      resolve(val || 'Anonymous');
    }
    function onKey(e) { if (e.key === 'Enter') submit(); }
    okBtn.addEventListener('click', submit);
    input.addEventListener('keydown', onKey);
  });
}

(async function initUserIdentity() {
  currentUserName = await window.api.getUserName();
  if (!currentUserName) {
    currentUserName = await showUserNameDialog('');
    await window.api.setUserName(currentUserName);
  }
  updateUserBadge();
})();

function updateUserBadge() {
  const el = document.getElementById('user-badge');
  if (el) el.textContent = '\uD83D\uDC64 ' + (currentUserName || 'Anonymous');
}

document.getElementById('user-badge').addEventListener('click', async () => {
  const newName = await showUserNameDialog(currentUserName);
  if (newName && newName !== currentUserName) {
    currentUserName = newName;
    await window.api.setUserName(currentUserName);
    updateUserBadge();
  }
});

// Picker is always the default mode on startup

// =====================================================================
// Tools tab + Segmentation tool
// =====================================================================
// Tool: 'segment' (draw rectangle → SAM segmentation) or null.
// Click the tool button to activate; click again (or Esc) to deactivate.

const previewTool = {
  active: null,
  busy: false,

  // Rectangle drawing state (coords are relative to #viewer-stage)
  drawing: false,
  startX: 0,
  startY: 0,
  rectDisplay: null,    // {x, y, w, h} in #viewer-stage CSS pixels
};

const segTool = {
  bgColor: 'white',
  maskOpacity: 0.5,

  imageEncoded: false,
  encodedImagePath: null,
  imageWidth: 0,            // actual original image dimensions (from SAM encode)
  imageHeight: 0,

  // Bounding box being drawn right now (normalized 0..1 coordinates)
  box: null,              // { x1, y1, x2, y2 } in 0..1 range, or null

  // Operation for the current drag: 'new' | 'add' | 'sub' based on modifier keys
  dragOp: 'new',

  // The combined selection mask (accumulates via add/subtract operations)
  currentMaskBase64: null,

  // Fine rotation (degrees) applied at Apply time
  rotation: 0,

  // Canvas references (set on init)
  maskCanvas: null,
  maskCtx: null,
  interCanvas: null,
  interCtx: null,

  // Marching ants animation
  edgePixels: null,       // cached list of boundary pixels { x, y, t } (t=x+y for dash phase)
  edgeCanvasSize: null,   // { w, h } the edge pixels were computed for
  antsOffset: 0,          // current dash phase offset
  antsRAF: null,          // requestAnimationFrame id
  antsLastTick: 0,        // time of last offset increment
};

function setActiveTool(toolName) {
  const newTool = (previewTool.active === toolName) ? null : toolName;
  previewTool.active = newTool;
  document.querySelectorAll('.tool-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tool === newTool);
  });
  document.getElementById('tool-options-segment').classList.toggle('visible', newTool === 'segment');
  dom.viewerStage.classList.toggle('tool-segment', newTool === 'segment');
  clearViewerRect();

  if (newTool === 'segment') {
    activateSegTool();
  } else {
    deactivateSegTool();
  }

  // The tool just activates. It only works when an image is open in the viewer,
  // so if the user isn't viewing one yet, give a hint instead of auto-opening.
  if (newTool && !isViewerOpen()) {
    setStatus('Open an image (double-click a thumbnail) to use the tool.');
  }
}

// --- Viewer rectangle (reused for segment bounding box) ---

function clearViewerRect() {
  previewTool.drawing = false;
  previewTool.rectDisplay = null;
  const overlay = document.getElementById('viewer-rect-overlay');
  if (overlay) overlay.classList.add('hidden');
}

function getDisplayedImageRect() {
  const img = dom.viewerImage;
  const stage = dom.viewerStage;
  if (!img || !stage) return null;

  const natW = img.naturalWidth;
  const natH = img.naturalHeight;
  if (!natW || !natH) return null;

  const stageRect = stage.getBoundingClientRect();
  const imgRect = img.getBoundingClientRect();

  const scale = Math.min(imgRect.width / natW, imgRect.height / natH);
  const drawW = natW * scale;
  const drawH = natH * scale;
  const offsetX = (imgRect.width - drawW) / 2 + (imgRect.left - stageRect.left);
  const offsetY = (imgRect.height - drawH) / 2 + (imgRect.top - stageRect.top);

  return { left: offsetX, top: offsetY, width: drawW, height: drawH, natW, natH };
}

function updateRectBox(box, r) {
  box.style.left = `${r.x}px`;
  box.style.top = `${r.y}px`;
  box.style.width = `${r.w}px`;
  box.style.height = `${r.h}px`;
}

// --- Segment tool: activation / state ---

function activateSegTool() {
  clearSegState();

  const container = document.getElementById('seg-canvas-container');
  container.classList.remove('hidden');
  container.classList.add('active');
  // Ensure no stale modifier-cursor classes from a previous session
  dom.viewerStage.classList.remove('mod-add', 'mod-sub');

  initSegCanvases();
  updateSegStatus('Draw a box. Shift+draw to add, Alt+draw to subtract.');
  updateSegActionButtons();
  refreshSegHistory();
}

// Reload the history list for the current viewer image
async function refreshSegHistory() {
  const listEl = document.getElementById('seg-history-list');
  if (!listEl) return;
  if (!viewerCurrentPath) {
    listEl.className = 'seg-history-empty';
    listEl.textContent = 'Open an image to see history.';
    updateSegSaveButton(false);
    return;
  }

  // Check if this image was already marked as saved earlier in the session
  try {
    const savedStatus = await window.api.segIsSaved(viewerCurrentPath);
    updateSegSaveButton(!!savedStatus?.saved);
  } catch (e) { updateSegSaveButton(false); }

  const data = await window.api.segGetHistory(viewerCurrentPath);
  const steps = data?.steps || [];
  const current = data?.current ?? -1;

  if (steps.length === 0) {
    listEl.className = 'seg-history-empty';
    listEl.textContent = 'No history yet.';
    return;
  }

  // Newest step first (top of list)
  const ordered = [...steps].sort((a, b) => b.step - a.step);

  listEl.className = '';
  listEl.innerHTML = '';
  for (const s of ordered) {
    const item = document.createElement('div');
    const isCurrent = s.step === current;
    item.className = 'seg-history-item' + (isCurrent ? ' seg-history-current' : '');
    const when = new Date(s.mtime);
    const label = s.step === 0 ? 'Original' : `Step ${s.step}`;
    item.innerHTML = `
      <span class="seg-history-marker">${isCurrent ? '\u25B6' : ''}</span>
      <div class="seg-history-label">
        <span>${label}</span>
        <span class="seg-history-time">${when.toLocaleString()}</span>
      </div>
    `;
    if (!isCurrent) {
      item.addEventListener('click', () => jumpToSegStep(s.step));
    }
    listEl.appendChild(item);
  }
}

async function markSegSaved() {
  if (!viewerCurrentPath) {
    setStatus('Open an image first.');
    return;
  }
  const ok = confirm('Mark this image as saved?\n\nThe history stays available for this session, but will be deleted when the app is restarted.');
  if (!ok) return;

  try {
    const result = await window.api.segMarkSaved(viewerCurrentPath);
    if (result && result.status === 'ok') {
      updateSegStatus('Saved. History will be cleaned up on next app start.');
      setStatus('Marked as saved.');
      updateSegSaveButton(true);
      // Return to the thumbnail grid — done editing this tablet
      if (previewTool.active) setActiveTool(previewTool.active);
      if (isViewerOpen()) exitViewerMode();
      // Switch right panel back to Structure — editing is done
      const structTab = document.querySelector('.right-tab[data-tab="structure"]');
      if (structTab) structTab.click();
    } else {
      updateSegStatus(`Save error: ${result?.error || 'failed'}`);
    }
  } catch (err) {
    updateSegStatus(`Save error: ${err.message}`);
  }
}

function updateSegSaveButton(isSaved) {
  const btn = document.getElementById('seg-save');
  if (!btn) return;
  if (isSaved) {
    btn.textContent = '\u2713 Saved';
    btn.disabled = true;
  } else {
    btn.innerHTML = '&#x1F4BE; Save';
    btn.disabled = false;
  }
}

async function jumpToSegStep(step) {
  if (!viewerCurrentPath) return;

  previewTool.busy = true;
  updateSegStatus(`Jumping to step ${step}...`);

  try {
    const result = await window.api.segJumpToStep(viewerCurrentPath, step);
    if (result && result.status === 'ok') {
      updateSegStatus(`Now at ${step === 0 ? 'Original' : 'step ' + step}.`);
      setStatus(`Jumped to ${step === 0 ? 'Original' : 'step ' + step}.`);

      if (result.thumbnail) {
        const card = getCardForImage(viewerCurrentPath);
        if (card) {
          const imgEl = card.querySelector('img');
          if (imgEl) imgEl.src = result.thumbnail;
        }
      }

      clearSegState();
      if (isViewerOpen()) await loadViewerImage(viewerCurrentPath);
      refreshSegHistory();
    } else {
      updateSegStatus(`Jump error: ${result?.error || 'failed'}`);
    }
  } catch (err) {
    updateSegStatus(`Jump error: ${err.message}`);
  }

  previewTool.busy = false;
}

function deactivateSegTool() {
  clearSegState();
  const container = document.getElementById('seg-canvas-container');
  container.classList.add('hidden');
  container.classList.remove('active');
  // Drop modifier-cursor classes
  dom.viewerStage.classList.remove('mod-add', 'mod-sub');
  clearSegCanvases();
}

function clearSegState() {
  segTool.box = null;
  segTool.currentMaskBase64 = null;
  segTool.imageEncoded = false;
  segTool.encodedImagePath = null;
  segTool.imageWidth = 0;
  segTool.imageHeight = 0;
  segTool.edgePixels = null;
  segTool.edgeCanvasSize = null;
  segTool.dragOp = 'new';
  segTool.rotation = 0;
  updateSegRotationUI();
  stopMarchingAntsAnimation();
  clearViewerRect();
  clearSegCanvases();
  updateSegActionButtons();
}

function updateSegRotationUI() {
  const slider = document.getElementById('seg-rotation');
  const num = document.getElementById('seg-rotation-num');
  if (slider) slider.value = segTool.rotation;
  if (num) num.value = segTool.rotation;
  applySegRotationPreview();
}

function applySegRotationPreview() {
  // Rotate only the mask/interaction canvases so the user sees the rotation live
  const maskC = segTool.maskCanvas;
  const interC = segTool.interCanvas;
  const t = `rotate(${segTool.rotation}deg)`;
  const origin = '50% 50%';
  if (maskC) { maskC.style.transformOrigin = origin; maskC.style.transform = t; }
  if (interC) { interC.style.transformOrigin = origin; interC.style.transform = t; }
}

function initSegCanvases() {
  segTool.maskCanvas = document.getElementById('seg-canvas-mask');
  segTool.interCanvas = document.getElementById('seg-canvas-interaction');
  segTool.maskCtx = segTool.maskCanvas.getContext('2d');
  segTool.interCtx = segTool.interCanvas.getContext('2d');
  resizeSegCanvases();
}

function resizeSegCanvases() {
  const disp = getDisplayedImageRect();
  if (!disp) return;

  for (const canvas of [segTool.maskCanvas, segTool.interCanvas]) {
    if (!canvas) continue;
    canvas.width = disp.width;
    canvas.height = disp.height;
    canvas.style.left = `${disp.left}px`;
    canvas.style.top = `${disp.top}px`;
    canvas.style.width = `${disp.width}px`;
    canvas.style.height = `${disp.height}px`;
  }
}

function clearSegCanvases() {
  if (segTool.maskCtx && segTool.maskCanvas) {
    segTool.maskCtx.clearRect(0, 0, segTool.maskCanvas.width, segTool.maskCanvas.height);
  }
  if (segTool.interCtx && segTool.interCanvas) {
    segTool.interCtx.clearRect(0, 0, segTool.interCanvas.width, segTool.interCanvas.height);
  }
}

// --- Coordinate conversion ---

function stageToCanvasCoords(stageX, stageY) {
  const disp = getDisplayedImageRect();
  if (!disp) return null;
  const cx = stageX - disp.left;
  const cy = stageY - disp.top;
  return {
    x: Math.max(0, Math.min(disp.width, cx)),
    y: Math.max(0, Math.min(disp.height, cy)),
  };
}

function canvasToImageCoords(canvasX, canvasY) {
  const disp = getDisplayedImageRect();
  if (!disp) return null;
  // Use the actual original image dimensions (from SAM encode) if available,
  // not the display-resolution natW/natH which may be a scaled-down preview.
  const targetW = segTool.imageWidth || disp.natW;
  const targetH = segTool.imageHeight || disp.natH;
  return {
    x: Math.round((canvasX / disp.width) * targetW),
    y: Math.round((canvasY / disp.height) * targetH),
  };
}

// --- Mouse handlers ---

function onViewerMouseDown(e) {
  if (previewTool.active !== 'segment' || previewTool.busy) return;
  if (!isViewerOpen()) return;
  if (e.button !== 0) return;

  const disp = getDisplayedImageRect();
  if (!disp) return;

  const stageRect = dom.viewerStage.getBoundingClientRect();
  const x = e.clientX - stageRect.left;
  const y = e.clientY - stageRect.top;

  // Only start drawing if the cursor is over the image
  if (x < disp.left || x > disp.left + disp.width ||
      y < disp.top || y > disp.top + disp.height) return;

  e.preventDefault();

  // Determine the operation from modifier keys (like Photoshop)
  if (e.shiftKey) segTool.dragOp = 'add';
  else if (e.altKey) segTool.dragOp = 'sub';
  else segTool.dragOp = 'new';

  previewTool.drawing = true;
  previewTool.startX = x;
  previewTool.startY = y;
  previewTool.rectDisplay = { x, y, w: 0, h: 0 };

  const overlay = document.getElementById('viewer-rect-overlay');
  const box = document.getElementById('viewer-rect-box');
  overlay.classList.remove('hidden');
  updateRectBox(box, previewTool.rectDisplay);
}

function onViewerMouseMove(e) {
  if (!previewTool.drawing) return;
  const stageRect = dom.viewerStage.getBoundingClientRect();
  const disp = getDisplayedImageRect();
  if (!disp) return;

  const x = Math.max(disp.left, Math.min(disp.left + disp.width, e.clientX - stageRect.left));
  const y = Math.max(disp.top, Math.min(disp.top + disp.height, e.clientY - stageRect.top));

  const rx = Math.min(previewTool.startX, x);
  const ry = Math.min(previewTool.startY, y);
  const rw = Math.abs(x - previewTool.startX);
  const rh = Math.abs(y - previewTool.startY);
  previewTool.rectDisplay = { x: rx, y: ry, w: rw, h: rh };

  updateRectBox(document.getElementById('viewer-rect-box'), previewTool.rectDisplay);
}

function onViewerMouseUp(e) {
  if (!previewTool.drawing) return;
  previewTool.drawing = false;

  // Refresh modifier cursor classes based on the CURRENT key state — prevents
  // a stuck '−' or '+' cursor if a modifier was released mid-drag outside the
  // window and we missed the keyup event.
  if (e) {
    dom.viewerStage.classList.toggle('mod-add', !!e.shiftKey);
    dom.viewerStage.classList.toggle('mod-sub', !!e.altKey && !e.shiftKey);
  }

  const r = previewTool.rectDisplay;
  if (!r || r.w < 6 || r.h < 6) {
    clearViewerRect();
    return;
  }

  const disp = getDisplayedImageRect();
  if (!disp) return;

  // Store box in normalized (0..1) coords — will be converted to image pixels
  // when sending to SAM (after encode returns the real image dimensions).
  segTool.box = {
    x1: (r.x - disp.left) / disp.width,
    y1: (r.y - disp.top) / disp.height,
    x2: (r.x - disp.left + r.w) / disp.width,
    y2: (r.y - disp.top + r.h) / disp.height,
  };

  updateSegActionButtons();

  // For an "add" or "sub" drag, we need an existing mask to combine with.
  // If none exists, silently treat it as a "new" selection.
  if (segTool.dragOp !== 'new' && !segTool.currentMaskBase64) {
    segTool.dragOp = 'new';
  }

  const opLabel = segTool.dragOp === 'add' ? 'Adding…'
                : segTool.dragOp === 'sub' ? 'Subtracting…'
                : 'Encoding image…';
  updateSegStatus(opLabel);

  // Run the SAM pipeline: encode (if needed) then predict for the new box
  requestSegEncode().then(() => runSegPredictionForDrag());
}

function renderSegMask(maskPngBase64) {
  if (!maskPngBase64 || !segTool.maskCtx || !segTool.maskCanvas) return;

  // Ensure canvases are correctly sized/positioned for the current image
  resizeSegCanvases();

  const img = new Image();
  img.onload = () => {
    const ctx = segTool.maskCtx;
    const w = segTool.maskCanvas.width;
    const h = segTool.maskCanvas.height;

    console.log('[seg] mask image:', img.naturalWidth, 'x', img.naturalHeight,
                '→ canvas:', w, 'x', h,
                'pos:', segTool.maskCanvas.style.left, segTool.maskCanvas.style.top);

    ctx.clearRect(0, 0, w, h);

    // Draw mask scaled to canvas size into a temp canvas
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = w;
    tempCanvas.height = h;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(img, 0, 0, w, h);
    const src = tempCtx.getImageData(0, 0, w, h).data;

    // Compute mask boundary pixels once and cache them. Animation just redraws
    // the cached list with a shifting dash offset → smooth marching-ants effect.
    function inside(x, y) {
      if (x < 0 || x >= w || y < 0 || y >= h) return false;
      return src[(y * w + x) * 4] > 128;
    }

    const edges = [];
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (!inside(x, y)) continue;
        if (inside(x - 1, y) && inside(x + 1, y) && inside(x, y - 1) && inside(x, y + 1)) continue;
        edges.push({ x, y, t: x + y });
      }
    }

    segTool.edgePixels = edges;
    segTool.edgeCanvasSize = { w, h };
    segTool.antsOffset = 0;
    startMarchingAntsAnimation();
  };
  img.src = `data:image/png;base64,${maskPngBase64}`;
}

// Redraw the cached edge pixels with the current dash offset.
function drawMarchingAnts() {
  if (!segTool.edgePixels || !segTool.maskCtx || !segTool.edgeCanvasSize) return;
  const { w, h } = segTool.edgeCanvasSize;
  if (w !== segTool.maskCanvas.width || h !== segTool.maskCanvas.height) return;

  const ctx = segTool.maskCtx;
  const out = ctx.createImageData(w, h);
  const outData = out.data;
  const DASH = 6;
  const offset = segTool.antsOffset;

  for (const p of segTool.edgePixels) {
    const alt = Math.floor((p.t + offset) / DASH) % 2;
    const color = alt === 0 ? 0 : 255;
    // Draw 2×2 block for thickness
    for (const [dx, dy] of [[0, 0], [1, 0], [0, 1]]) {
      const nx = p.x + dx, ny = p.y + dy;
      if (nx < 0 || nx >= w || ny < 0 || ny >= h) continue;
      const idx = (ny * w + nx) * 4;
      outData[idx]     = color;
      outData[idx + 1] = color;
      outData[idx + 2] = color;
      outData[idx + 3] = 255;
    }
  }
  ctx.putImageData(out, 0, 0);
}

function startMarchingAntsAnimation() {
  stopMarchingAntsAnimation();
  segTool.antsLastTick = performance.now();
  const tick = (now) => {
    // Shift the dash phase ~1 pixel every ~60ms → comfortable crawl speed
    if (now - segTool.antsLastTick >= 60) {
      segTool.antsOffset = (segTool.antsOffset + 1) % 120;
      segTool.antsLastTick = now;
      drawMarchingAnts();
    }
    segTool.antsRAF = requestAnimationFrame(tick);
  };
  // Render the initial frame immediately
  drawMarchingAnts();
  segTool.antsRAF = requestAnimationFrame(tick);
}

function stopMarchingAntsAnimation() {
  if (segTool.antsRAF) {
    cancelAnimationFrame(segTool.antsRAF);
    segTool.antsRAF = null;
  }
}

// --- UI controls ---

function setSegBg(color) {
  segTool.bgColor = color;
  document.getElementById('seg-bg-white').classList.toggle('active', color === 'white');
  document.getElementById('seg-bg-black').classList.toggle('active', color === 'black');
}

function updateSegStatus(msg) {
  const el = document.getElementById('seg-status');
  if (el) el.textContent = msg;
}

function updateSegActionButtons() {
  const hasBox = !!segTool.box;
  const hasMask = !!segTool.currentMaskBase64;
  document.getElementById('seg-clear').disabled = !hasBox && !hasMask;
  document.getElementById('seg-apply').disabled = !hasMask;
  // Rotation row only makes sense once a mask exists
  const rotRow = document.getElementById('seg-rotation-row');
  if (rotRow) rotRow.style.display = hasMask ? '' : 'none';
}

function segClear() {
  clearSegState();
  updateSegStatus('Draw a box. Shift+draw to add, Alt+draw to subtract.');
}

// --- Backend communication ---
// SAM ONNX sessions are preloaded at app startup during the splash screen
// (see src/main/main.js app.whenReady). By the time the user can interact
// with the UI, segmentation is already ready. sam.init() in sam-onnx.js
// is idempotent and will lazy-init on first encode() as a safety net if
// preload ever failed.

async function requestSegEncode() {
  if (!viewerCurrentPath) return;
  if (segTool.encodedImagePath === viewerCurrentPath) return;

  previewTool.busy = true;
  updateSegStatus('Encoding image (this takes a few seconds)...');

  try {
    const result = await window.api.segEncodeImage(viewerCurrentPath);
    if (result && result.status === 'ready') {
      segTool.imageEncoded = true;
      segTool.encodedImagePath = viewerCurrentPath;
      segTool.imageWidth = result.width;
      segTool.imageHeight = result.height;
    } else {
      updateSegStatus(`Encode failed: ${result?.error || 'unknown'}`);
    }
  } catch (err) {
    updateSegStatus(`Encode error: ${err.message}`);
  }

  previewTool.busy = false;
}

// Run SAM on the current box and combine the result with the existing mask
// based on segTool.dragOp ('new' | 'add' | 'sub').
async function runSegPredictionForDrag() {
  if (!segTool.imageEncoded || !segTool.box) return;
  previewTool.busy = true;

  try {
    // Convert normalized box to image pixel coords
    const iw = segTool.imageWidth;
    const ih = segTool.imageHeight;
    const pixelBox = {
      x1: Math.round(segTool.box.x1 * iw),
      y1: Math.round(segTool.box.y1 * ih),
      x2: Math.round(segTool.box.x2 * iw),
      y2: Math.round(segTool.box.y2 * ih),
    };

    // Predict the mask for ONLY the new box — no points
    const result = await window.api.segPredictMask(pixelBox, [], []);
    if (!result || !result.mask) {
      updateSegStatus(`Prediction failed: ${result?.error || 'unknown'}`);
      previewTool.busy = false;
      return;
    }

    // Merge with the existing mask based on the drag operation
    let finalMask;
    if (segTool.dragOp === 'new' || !segTool.currentMaskBase64) {
      finalMask = result.mask;
    } else if (segTool.dragOp === 'add') {
      finalMask = await mergeMasksBase64(segTool.currentMaskBase64, result.mask, 'union');
    } else if (segTool.dragOp === 'sub') {
      finalMask = await mergeMasksBase64(segTool.currentMaskBase64, result.mask, 'subtract');
    } else {
      finalMask = result.mask;
    }

    segTool.currentMaskBase64 = finalMask;
    clearViewerRect();
    renderSegMask(finalMask);

    const verb = segTool.dragOp === 'add' ? 'Added to' : segTool.dragOp === 'sub' ? 'Subtracted from' : 'Created new';
    updateSegStatus(`${verb} selection. Apply to save.`);
    updateSegActionButtons();

    // Reset dragOp after applying (so next plain drag defaults to 'new')
    segTool.dragOp = 'new';
    segTool.box = null;
  } catch (err) {
    updateSegStatus(`Prediction error: ${err.message}`);
  }

  previewTool.busy = false;
}

/**
 * Merge two base64 grayscale PNG masks pixel-wise.
 * op = 'union' (OR) | 'subtract' (A AND NOT B).
 * Returns a new base64 PNG.
 */
function mergeMasksBase64(baseB64, newB64, op) {
  return new Promise((resolve, reject) => {
    const imgA = new Image();
    const imgB = new Image();
    let loaded = 0;
    function onLoad() {
      loaded++;
      if (loaded < 2) return;

      const w = Math.max(imgA.naturalWidth, imgB.naturalWidth);
      const h = Math.max(imgA.naturalHeight, imgB.naturalHeight);
      const canvasA = document.createElement('canvas');
      const canvasB = document.createElement('canvas');
      canvasA.width = w; canvasA.height = h;
      canvasB.width = w; canvasB.height = h;
      const ctxA = canvasA.getContext('2d');
      const ctxB = canvasB.getContext('2d');
      ctxA.drawImage(imgA, 0, 0, w, h);
      ctxB.drawImage(imgB, 0, 0, w, h);
      const dataA = ctxA.getImageData(0, 0, w, h);
      const dataB = ctxB.getImageData(0, 0, w, h).data;
      const a = dataA.data;

      for (let i = 0; i < a.length; i += 4) {
        const va = a[i] > 128 ? 255 : 0;
        const vb = dataB[i] > 128 ? 255 : 0;
        let v;
        if (op === 'union') v = Math.max(va, vb);
        else if (op === 'subtract') v = (va === 255 && vb === 0) ? 255 : 0;
        else v = vb;
        a[i] = a[i + 1] = a[i + 2] = v;
        a[i + 3] = 255;
      }

      ctxA.putImageData(dataA, 0, 0);
      const dataUrl = canvasA.toDataURL('image/png');
      const b64 = dataUrl.split(',')[1];
      resolve(b64);
    }
    imgA.onload = onLoad;
    imgB.onload = onLoad;
    imgA.onerror = reject;
    imgB.onerror = reject;
    imgA.src = `data:image/png;base64,${baseB64}`;
    imgB.src = `data:image/png;base64,${newB64}`;
  });
}

async function applySegMask() {
  if (!segTool.currentMaskBase64 || !viewerCurrentPath) return;

  previewTool.busy = true;
  updateSegStatus('Applying mask...');

  try {
    const result = await window.api.segApplyMask(
      viewerCurrentPath,
      null,  // main process computes _cleaned/ path
      segTool.currentMaskBase64,
      segTool.bgColor,
      segTool.rotation
    );

    if (result && result.status === 'ok') {
      updateSegStatus(`Image saved. Mask saved as _mask.png.`);
      setStatus('Segmentation applied successfully.');

      if (result.thumbnail) {
        const card = getCardForImage(viewerCurrentPath);
        if (card) {
          const imgEl = card.querySelector('img');
          if (imgEl) imgEl.src = result.thumbnail;
        }
      }

      // Reset segmentation state and reload the viewer with the new (cropped) file
      clearSegState();
      if (isViewerOpen()) {
        await loadViewerImage(viewerCurrentPath);
      }
      refreshSegHistory();
    } else {
      updateSegStatus(`Apply error: ${result?.error || 'failed'}`);
    }
  } catch (err) {
    updateSegStatus(`Apply error: ${err.message}`);
  }

  previewTool.busy = false;
}

// Update the Image Info section in the Tools tab
function updateToolInfo() {
  const filenameEl = document.getElementById('info-filename');
  const viewEl = document.getElementById('info-view');
  const dimsEl = document.getElementById('info-dims');
  if (!filenameEl) return;

  const path = viewerCurrentPath || state.selectedImage;
  if (!path) {
    filenameEl.textContent = '—';
    viewEl.textContent = '—';
    dimsEl.textContent = '—';
    return;
  }

  const img = state.images.find(i => i.path === path);
  filenameEl.textContent = img ? img.name : '—';
  const code = state.assignments[path];
  viewEl.textContent = code ? `${VIEW_CODES[code]} (_${code})` : 'unassigned';

  window.api.getImageInfo(path).then(info => {
    if (info && (viewerCurrentPath === path || state.selectedImage === path)) {
      dimsEl.textContent = `${info.width}\u00D7${info.height}`;
    }
  });
}

// --- Wire up tool panel ---
document.querySelectorAll('.tool-btn').forEach(btn => {
  btn.addEventListener('click', () => setActiveTool(btn.dataset.tool));
});

// Segment tool controls
document.getElementById('seg-bg-white').addEventListener('click', () => setSegBg('white'));
document.getElementById('seg-bg-black').addEventListener('click', () => setSegBg('black'));
document.getElementById('seg-clear').addEventListener('click', segClear);
document.getElementById('seg-apply').addEventListener('click', applySegMask);
document.getElementById('seg-save').addEventListener('click', markSegSaved);
document.getElementById('seg-opacity').addEventListener('input', (e) => {
  segTool.maskOpacity = e.target.value / 100;
  if (segTool.maskCanvas) segTool.maskCanvas.style.opacity = segTool.maskOpacity;
  document.getElementById('seg-opacity-value').textContent = `${e.target.value}%`;
});

// Rotation: slider + number input stay in sync; preview updates live
function setSegRotation(val) {
  const clamped = Math.max(-180, Math.min(180, Number(val) || 0));
  segTool.rotation = clamped;
  const slider = document.getElementById('seg-rotation');
  const num = document.getElementById('seg-rotation-num');
  // Only set if different to avoid feedback loops
  if (slider && parseFloat(slider.value) !== clamped) slider.value = clamped;
  if (num && parseFloat(num.value) !== clamped) num.value = clamped;
  applySegRotationPreview();
}
document.getElementById('seg-rotation').addEventListener('input', (e) => setSegRotation(e.target.value));
document.getElementById('seg-rotation-num').addEventListener('input', (e) => setSegRotation(e.target.value));
document.getElementById('seg-rotation-reset').addEventListener('click', () => setSegRotation(0));

// Modifier-key cursor feedback (only relevant when the segment tool is active)
function updateSegModifierCursor(e) {
  if (previewTool.active !== 'segment') {
    dom.viewerStage.classList.remove('mod-add', 'mod-sub');
    return;
  }
  dom.viewerStage.classList.toggle('mod-add', !!e.shiftKey);
  dom.viewerStage.classList.toggle('mod-sub', !!e.altKey && !e.shiftKey);
}
window.addEventListener('keydown', updateSegModifierCursor);
window.addEventListener('keyup', updateSegModifierCursor);
// On window focus or mouse entering the stage, assume no modifiers are held
// unless explicit key events say otherwise.
window.addEventListener('blur', () => dom.viewerStage.classList.remove('mod-add', 'mod-sub'));
dom.viewerStage.addEventListener('mouseenter', () => dom.viewerStage.classList.remove('mod-add', 'mod-sub'));

dom.viewerStage.addEventListener('mousedown', onViewerMouseDown);
// Zoom (wheel) and pan (middle-mouse) on the viewer
dom.viewerStage.addEventListener('wheel', onViewerWheel, { passive: false });
dom.viewerStage.addEventListener('mousedown', onViewerPanStart);
window.addEventListener('mousemove', onViewerPanMove);
window.addEventListener('mouseup', onViewerPanEnd);
// Disable the default context menu on the stage so middle/right-click pans cleanly
dom.viewerStage.addEventListener('auxclick', (e) => e.preventDefault());
window.addEventListener('mousemove', onViewerMouseMove);
window.addEventListener('mouseup', onViewerMouseUp);

// Resize: reposition canvases and drop stale rect
window.addEventListener('resize', () => {
  clearViewerRect();
  if (previewTool.active === 'segment') resizeSegCanvases();
});
