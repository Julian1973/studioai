(function () {
  "use strict";

  const app = {
    episode: "Ep1",
    scene: "1",
    shotId: null,
    view: "pipeline",
    pipelineStep: "upload",
    session: null,
    roster: null,
    references: null,
    referenceStage: "keyframe",
    selectedCandidate: null,
    pendingAction: null,
    pendingAdvance: null,
    voiceStatus: null,
    voiceStatusKey: null,
    voiceLoading: false,
    roughCutStatus: null,
    roughCutStatusKey: null,
    roughCutLoading: false,
    pollTimer: null,
    toastTimer: null,
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const esc = (value) => String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  async function api(path, options) {
    const response = await fetch(path, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let payload = {};
    try { payload = await response.json(); } catch (_) { payload = {}; }
    if (!response.ok) {
      const error = new Error(payload.error || `Request failed (${response.status})`);
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  const pipelineSteps = [
    { id: "upload", label: "Upload", phase: "Pre-Prod", step: 1 },
    { id: "style", label: "Style", phase: "Pre-Prod", step: 2 },
    { id: "analysis", label: "Analysis", phase: "Pre-Prod", step: 3 },
    { id: "characters", label: "Characters", phase: "Design", step: 4 },
    { id: "props", label: "Props", phase: "Design", step: 5 },
    { id: "locations", label: "Locations", phase: "Design", step: 6 },
    { id: "storyboard", label: "Storyboard", phase: "Production", step: 7 },
    { id: "audio", label: "Audio", phase: "Production", step: 8 },
    { id: "footage", label: "Footage", phase: "Production", step: 9 },
    { id: "rough-cut", label: "Rough Cut", phase: "Production", step: 10 },
  ];

  const characterRoster = [
    {
      name: "Zenny",
      scenes: "1-10",
      status: "ready",
      role: "Calm, graceful Crystal Bear, precise and composed counterpart to Fuzzby",
      identity: "Small anthropomorphic bear with soft lavender-purple fur, smooth oval face, almond-shaped eyes, small rounded nose, soft rounded cheeks and neat arched eyebrows.",
      reference: "Generate Reference Sheet",
      wardrobes: [{ label: "Zenny — Rainforest/Crystal Cove Default", scenes: "1-10", state: "regen", initial: "Z" }],
    },
    {
      name: "Aida",
      scenes: "2, 6, 7, 8, 9, 10",
      status: "ready",
      role: "Wise, serene leader of the Crystal Bears, healer and guide",
      identity: "Medium-sized cream-white anthropomorphic bear with a graceful oval face, large gentle almond-shaped eyes, soft rounded nose and elegant arched eyebrows.",
      reference: "Generate Reference Sheet",
      wardrobes: [{ label: "Aida — Crystal Cove Default", scenes: "2, 6, 7, 8, 9, 10", state: "regen", initial: "A" }],
    },
    {
      name: "Keen",
      scenes: "3, 4, 7, 8, 9, 10",
      status: "pending",
      role: "Protagonist, brave young bear setting out on his first adventure",
      identity: "Small-to-medium young bear with warm mid-brown fur, round youthful face, wide bright eyes, small button nose and full rounded cheeks.",
      reference: "Generate a wardrobe first",
      wardrobes: [
        { label: "Keen — Pier Departure, Dry", scenes: "3", state: "gen", initial: "K" },
        { label: "Keen — At Sea and Storm, Soaked", scenes: "4, 7", state: "gen", initial: "K" },
        { label: "Keen — Crystal Cove Beach, Post-Storm", scenes: "8, 9, 10", state: "gen", initial: "K" },
      ],
    },
    {
      name: "Keen's Mum",
      scenes: "3",
      status: "pending",
      role: "Keen's devoted and proud mother, emotional at her son's departure",
      identity: "Medium warm mid-brown bear with a warm oval face, soft wide eyes, rounded nose, full cheeks and gentle rounded jawline.",
      reference: "Generate a wardrobe first",
      wardrobes: [{ label: "Keen's Mum — Pier Farewell", scenes: "3", state: "gen", initial: "K" }],
    },
    {
      name: "Howey",
      scenes: "6, 7, 8, 9, 10",
      status: "pending",
      role: "Crystal Bear, enthusiastic and protective member of the group",
      identity: "Medium teal-blue bear with a broad round face, large round eyes, wide flat nose, full cheeks and strong rounded jawline.",
      reference: "Generate a wardrobe first",
      wardrobes: [{ label: "Howey — Crystal Cove Default", scenes: "6, 7, 8, 9, 10", state: "gen", initial: "H" }],
    },
    {
      name: "Misty",
      scenes: "6, 7, 8, 9, 10",
      status: "pending",
      role: "Crystal Bear, warm and expressive member of the group",
      identity: "Small-to-medium silver-grey bear with a soft oval face, wide expressive eyes, delicate rounded nose and soft full cheeks.",
      reference: "Generate a wardrobe first",
      wardrobes: [{ label: "Misty — Crystal Cove Default", scenes: "6, 7, 8, 9, 10", state: "gen", initial: "M" }],
    },
    {
      name: "Luna",
      scenes: "6, 7, 8, 9, 10",
      status: "pending",
      role: "Crystal Bear, quiet and gentle member of the group",
      identity: "Small deep indigo-navy bear with a delicate oval face, soft half-moon eyes, small pointed nose and slender rounded jawline.",
      reference: "Generate a wardrobe first",
      wardrobes: [{ label: "Luna — Crystal Cove Default", scenes: "6, 7, 8, 9, 10", state: "gen", initial: "L" }],
    },
    {
      name: "Sunny",
      scenes: "8, 9, 10",
      status: "pending",
      role: "Crystal Bear, bright and enthusiastic member of the group",
      identity: "Small bright yellow bear with a round cheerful face, large sparkling eyes, small button nose and high expressive eyebrows.",
      reference: "Generate a wardrobe first",
      wardrobes: [{ label: "Sunny — Crystal Cove Default", scenes: "8, 9, 10", state: "gen", initial: "S" }],
    },
    {
      name: "Amie",
      scenes: "8, 9, 10",
      status: "pending",
      role: "Crystal Bear, warm and welcoming member of the group",
      identity: "Small rose-pink bear with a soft round face, wide warm eyes, soft rounded nose, full cheeks and gentle rounded jawline.",
      reference: "Generate a wardrobe first",
      wardrobes: [{ label: "Amie — Crystal Cove Default", scenes: "8, 9, 10", state: "gen", initial: "A" }],
    },
    {
      name: "Squeaky",
      scenes: "4, 7, 8, 9, 10",
      status: "pending",
      role: "Friendly dolphin companion who guides Keen through the storm and is rescued by him",
      identity: "Atlantic bottlenose dolphin with streamlined body, rounded melon forehead, short beak, bright side-set eyes and silver-grey dorsal colouring.",
      reference: "Generate a wardrobe first",
      wardrobes: [
        { label: "Squeaky — Open Water, Healthy", scenes: "4", state: "gen", initial: "S" },
        { label: "Squeaky — Storm, Entangled", scenes: "7", state: "gen", initial: "S" },
        { label: "Squeaky — Post-Rescue, Free", scenes: "8, 9, 10", state: "gen", initial: "S" },
      ],
    },
    {
      name: "Fuzzby",
      scenes: "0",
      status: "ready",
      role: "Needs canon role imported into this EP1 package",
      identity: "Identity present in existing reference image; fixed physical-trait text still needs to be completed in the package.",
      reference: "Generate Reference Sheet",
      wardrobes: [{ label: "Default look", scenes: "-", state: "regen", initial: "F" }],
    },
  ];

  const styleFamilies = [
    {
      group: "Photo & Illustration",
      options: [
        ["Cinematic Realism", "Photorealistic film look with dramatic lighting and depth of field"],
        ["Anime", "Japanese animation style with bold lines and vivid colors"],
        ["Film Noir", "High contrast black and white with deep shadows and moody atmosphere"],
        ["Watercolor", "Soft painted look with fluid washes and organic textures"],
        ["Graphic Novel", "Bold ink lines, halftone dots, and saturated comic book colors"],
        ["3D Animation", "Pixar-style 3D rendering with stylized characters and environments"],
      ],
    },
    {
      group: "2D Animated Explainer",
      options: [
        ["Flat Vector Explainer", "Bold flat vector shapes, saturated palette and clean edges"],
        ["Lined Illustration", "Hand-drawn outlines with textured fills and warm organic shapes"],
        ["Isometric Explainer", "Technical 2.5D perspective, clean vector lines and infographic polish"],
      ],
    },
    {
      group: "3D Motion Graphics",
      options: [
        ["3D Product Showcase", "Studio-lit product renders with turntable reveals"],
        ["Abstract Motion", "Kinetic sculpture, geometric primitives and metallic shaders"],
        ["Tech Motion Graphics", "Data visualization, HUD overlays and holographic UI"],
      ],
    },
  ];

  const aspectRatios = [
    ["16:9", "Widescreen"],
    ["2.39:1", "Anamorphic"],
    ["4:3", "Classic TV"],
    ["1:1", "Square"],
    ["9:16", "Vertical"],
    ["21:9", "Ultrawide"],
  ];

  const propRoster = [
    ["Aida's Rose Quartz Pendant", "2, 6, 9", "Generated", "A smooth polished rose quartz crystal pendant hanging on a fine natural cord, pale semi-translucent pink stone with a soft warm inner glow."],
    ["Crystal Singing Bowl and Wand", "2", "Draft", "A clear polished quartz crystal singing bowl with a padded cloth-tipped wooden wand, isolated on a neutral grey studio backdrop."],
    ["Keen's Father's Wristbands", "3, 4, 7, 8, 9, 10", "Draft", "A pair of worn aged leather wristbands with small aquamarine crystal gems glowing softly with azure light."],
    ["Keen's Small Sailboat", "3, 4, 7", "Draft", "A compact wooden single-mast sailboat with plain white sail, rope rigging and natural wood grain."],
    ["Keen's Satchel", "3, 4", "Draft", "A small worn canvas traveller's satchel with buckled flap closure and shoulder strap."],
    ["Drift Net", "7", "Draft", "A ragged discarded fishing drift net, frayed and tangled with weathered dark grey-green mesh."],
    ["Pollen Sacks", "1", "Draft", "Tiny round fuzzy pollen collection sacks dusted heavily in bright yellow pollen powder."],
  ];

  const locationRoster = [
    ["Deep Within the Rainforest", "Warm, lush, playful, gently ominous as storm approaches", "1", "A dense tropical rainforest interior with towering flowers, drifting pollen, dappled golden sunlight and a cooler storm shift."],
    ["Crystal Cove – Aida's Sanctuary", "Serene, mystical, meditative, softly glowing", "2", "A sheltered coastal cove with calm turquoise water, pale sand, rose quartz crystals and a carved crystal bowl."],
    ["Keen's Island – The Pier", "Tender, bittersweet, hopeful, quietly emotional", "3", "A modest wooden pier, compact sailboat, soft green island hills and bright reflective water."],
    ["At Sea", "Adventurous, open, then stormy and dangerous", "4, 7", "Open ocean clean plates that move from hopeful daylight to rough storm water and low steel-grey skies."],
  ];

  const sceneRoster = [
    ["1", "EXT. DEEP WITHIN THE RAINFOREST – DAY", "3/16"],
    ["2", "EXT. CRYSTAL COVE – AIDA'S SANCTUARY – DAY", "0/8"],
    ["3", "EXT. KEEN'S ISLAND – THE PIER – DAY", "0/18"],
    ["4", "EXT. AT SEA – DAY", "0/10"],
    ["5", "EXT. RAINFOREST EDGE – CONTINUOUS", "0/8"],
    ["6", "EXT. CRYSTAL COVE – STORM BUILDING", "0/16"],
    ["7", "EXT. OUT AT SEA – STORM", "0/20"],
    ["8", "EXT. CRYSTAL COVE BEACH – DAY", "0/12"],
    ["9", "EXT. GATHERING AREA – DAY", "0/10"],
    ["10", "EXT. CRYSTAL COVE BEACH – CONTINUOUS", "0/8"],
  ];

  const storyboardShots = [
    { shot: "01", status: "Regen", refs: ["LOC", "CHAR", "SB"], title: "DEEP WITHIN", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "02", status: "Regen", refs: ["SB", "CHAR", "SB"], title: "FUZZBY", characters: ["ZENNY"], setup: "" },
    { shot: "03", status: "Regen", refs: ["SB", "SB", "CHAR"], title: "FUZZBY", characters: [], setup: "" },
    { shot: "04", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S04", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "05", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S05", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "06", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S06", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "07", status: "Gen", refs: ["SB", "SB", "CHAR"], title: "S07", characters: ["FUZZBY"], setup: "" },
    { shot: "08", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S08", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "09", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S09", characters: ["FUZZBY"], setup: "" },
    { shot: "10", status: "Gen", refs: ["SB", "SB", "CHAR"], title: "S10", characters: ["FUZZBY"], setup: "" },
    { shot: "11", status: "Gen", refs: ["SB", "SB", "CHAR"], title: "S11", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "12", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S12", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "13", status: "Gen", refs: ["SB", "SB", "CHAR"], title: "S13", characters: ["FUZZBY"], setup: "recycled S10 setup" },
    { shot: "14", status: "Gen", refs: ["SB", "SB", "CHAR"], title: "S14", characters: ["FUZZBY", "ZENNY"], setup: "recycled S11 setup" },
    { shot: "15", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S15", characters: ["FUZZBY", "ZENNY"], setup: "" },
    { shot: "16", status: "Gen", refs: ["SB", "SB", "CHAR", "CHAR"], title: "S16", characters: ["FUZZBY", "ZENNY"], setup: "" },
  ];

  const footageClips = [
    {
      id: "Clip 1",
      shots: "Shot 1",
      state: "failed",
      count: "1 shot · 15s",
      references: ["Deep Within the Rainforest", "Zenny Wardrobe", "Uploaded"],
      startFrames: ["!"],
      prompt: "Shot 1: Extreme wide, 18mm, slow crane down through canopy. Camera descends through enormous tropical flowers, warm amber god rays and floating pollen motes. Tiny Fuzzby and Zenny weave between flower stems with pollen sacks visible on their back legs.",
      cost: "Generate · 660 tkn · $6.60",
    },
    {
      id: "Clip 2",
      shots: "Shots 2, 3, 4",
      state: "ready",
      count: "3 shots · 15s",
      references: ["Deep Within the Rainforest", "Fuzzby Wardrobe", "Zenny Wardrobe"],
      startFrames: ["S4"],
      prompt: "ENGLISH DIALOGUE ONLY. Shot 1: Medium tracking shot. Zenny glides with balletic precision while Fuzzby zig-zags chaotically behind her. FUZZBY: BIZZY-BIZZY-BIZZY. Cut to. Shot 2: Close-up. Fuzzby dives nose-first into pollen, clips a leaf, tumbles, then catches himself. FUZZBY: Nailed it. Cut to. Shot 3: Medium close-up. Zenny hovers perfectly still beside him, amused and unimpressed.",
      cost: "Regen · 660 tkn · $6.60",
    },
    {
      id: "Clip 3",
      shots: "Shots 5, 6, 7",
      state: "ready",
      count: "3 shots · 15s",
      references: ["Deep Within the Rainforest", "Fuzzby Wardrobe", "Zenny Wardrobe"],
      startFrames: ["S5", "S6", "S7"],
      prompt: "ENGLISH DIALOGUE ONLY. Shot 1: Close-up. Fuzzby emerges with a thick pollen moustache. FUZZBY: Do I look official? Cut to. Shot 2: Two-shot. Zenny laughs as Fuzzby smears the pollen worse. ZENNY: Yes Fuzzby. Officially nuts! Cut to. Shot 3: Wide shot. Fuzzby tumbles into a blossom and pops back out in a golden dust cloud.",
      cost: "Regen · 660 tkn · $6.60",
    },
    {
      id: "Clip 4",
      shots: "Shots 8, 9, 10",
      state: "ready",
      count: "3 shots · 15s",
      references: ["Deep Within the Rainforest", "Fuzzby Wardrobe", "Zenny Wardrobe"],
      startFrames: ["S8", "S9", "S10"],
      prompt: "ENGLISH DIALOGUE ONLY. Shot 1: Medium shot. Zenny smiles while Fuzzby hums louder and becomes completely golden with pollen. Cut to. Shot 2: Wide shot. A distant rumble rolls through the rainforest and the warm light cools. Cut to. Shot 3: Close-up. Fuzzby's expression shifts from joy to uncertainty as the storm enters the story.",
      cost: "Regen · 660 tkn · $6.60",
    },
  ];

  const editorClips = ["S1 C2", "S1 C3", "S1 C4", "S1 C5", "S1 C6", "S2 C1"];

  function readHash() {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    app.view = ["pipeline", "episodes", "director", "review"].includes(params.get("view"))
      ? params.get("view") : "pipeline";
    app.scene = params.get("scene") || "1";
    app.shotId = params.get("shot") || null;
    const requestedStep = { keyframes: "storyboard", animate: "footage", stitch: "rough-cut", post: "rough-cut" }[params.get("step")] || params.get("step");
    app.pipelineStep = pipelineSteps.some((step) => step.id === requestedStep)
      ? requestedStep : "upload";
  }

  function writeHash() {
    const params = new URLSearchParams({ view: app.view, scene: app.scene });
    if (app.shotId) params.set("shot", app.shotId);
    if (app.view === "pipeline") params.set("step", app.pipelineStep);
    const next = `#${params.toString()}`;
    if (location.hash !== next) history.replaceState(null, "", next);
  }

  function setView(view) {
    app.view = view;
    $$(".studio-view").forEach((node) => {
      const active = node.id === `view-${view}`;
      node.hidden = !active;
      node.classList.toggle("active", active);
    });
    $$('[data-view]').forEach((button) => button.classList.toggle(
      "active", button.dataset.view === view));
    writeHash();
    $("#workspace").scrollTo({ top: 0, behavior: "smooth" });
    if (view === "pipeline") renderPipeline();
  }

  function toast(message, isError) {
    const node = $("#toast");
    clearTimeout(app.toastTimer);
    node.textContent = message;
    node.hidden = false;
    node.classList.toggle("error", Boolean(isError));
    app.toastTimer = setTimeout(() => { node.hidden = true; }, isError ? 6000 : 3200);
  }

  function phaseLabel(phase) {
    return {
      story: "STORY & DIRECTION",
      keyframe: "OPENING FRAME",
      voice: "VOICE PERFORMANCE",
      animation: "ANIMATION",
      review: "DIRECTOR REVIEW",
      final: "FINAL MASTER",
    }[phase] || "CURRENT STEP";
  }

  function statusText(state) {
    return {
      complete: "Accepted",
      awaiting: "Review",
      ready: "Ready",
      blocked: "Needs attention",
      locked: "Waiting",
    }[state] || "Waiting";
  }

  function renderShotSwitcher(session) {
    const host = $("#shot-switcher");
    host.innerHTML = (session.shots || []).map((shot) => `
      <button type="button" data-shot="${esc(shot.shotId)}"
        class="${shot.selected ? "active" : ""} ${shot.state === "complete" ? "complete" : ""}">
        Shot ${shot.number}${shot.durationSec ? ` · ${Number(shot.durationSec)}s` : ""}
      </button>`).join("");
    host.querySelectorAll("[data-shot]").forEach((button) => button.addEventListener("click", () => {
      app.shotId = button.dataset.shot;
      writeHash();
      loadSession();
    }));
  }

  function resetShotScopedState() {
    app.voiceStatus = null;
    app.voiceStatusKey = null;
    app.voiceLoading = false;
    app.references = null;
    app.selectedCandidate = null;
  }

  function renderProductionNavigator(step) {
    if (!["storyboard", "audio", "footage", "rough-cut"].includes(step.id)) return "";
    const scenes = app.roster?.scenes || [];
    const shots = app.session?.shots || [];
    return `<nav class="production-navigator" aria-label="Episode scenes and shots">
      <div class="production-nav-row">
        <span class="production-nav-label">Scene</span>
        <div class="production-nav-options">
          ${scenes.map((scene) => {
            const number = String(scene.sceneNumber);
            return `<button type="button" data-production-scene="${esc(number)}" class="${number === app.scene ? "active" : ""}" aria-current="${number === app.scene ? "true" : "false"}" title="Scene ${esc(number)} · ${esc(scene.location || "")}">${esc(number)}<span>${esc(scene.location || `Scene ${number}`)}</span></button>`;
          }).join("") || '<span class="production-nav-empty">No approved scenes</span>'}
        </div>
      </div>
      <div class="production-nav-row">
        <span class="production-nav-label">Shot</span>
        <div class="production-nav-options shot-options">
          ${shots.map((shot) => `<button type="button" data-production-shot="${esc(shot.shotId)}" class="${shot.selected ? "active" : ""} ${shot.state === "complete" ? "complete" : ""}" aria-current="${shot.selected ? "true" : "false"}">Shot ${Number(shot.number)}${shot.durationSec ? `<span>${Number(shot.durationSec)}s</span>` : ""}</button>`).join("") || '<span class="production-nav-empty">Shots appear after direction</span>'}
        </div>
      </div>
    </nav>`;
  }

  function emptyStage(message, loading) {
    return `<div class="stage-empty">${loading ? '<span class="loading-mark" aria-hidden="true"></span>' : ""}<p>${esc(message)}</p></div>`;
  }

  function renderArtifact(session) {
    const stage = $("#media-stage");
    const artifact = session.artifact || {};
    app.selectedCandidate = null;
    if (session.status === "rendering") {
      stage.innerHTML = emptyStage(session.runningJob?.step || "Building the next result...", true);
      return;
    }
    if (artifact.type === "image" && artifact.url) {
      stage.innerHTML = `<span class="stage-badge">${esc(artifact.label || "Current image")}</span><img src="${esc(artifact.url)}?v=${Date.now()}" alt="${esc(artifact.label || "Current production image")}">`;
      return;
    }
    if (artifact.type === "audio" && artifact.url) {
      stage.innerHTML = `<span class="stage-badge">${esc(artifact.label || "Performance")}</span><audio controls preload="metadata" src="${esc(artifact.url)}?v=${Date.now()}"></audio>`;
      return;
    }
    if (artifact.type === "video" && artifact.url) {
      stage.innerHTML = `<span class="stage-badge">${esc(artifact.label || "Accepted animation")}</span><video controls playsinline preload="metadata" src="${esc(artifact.url)}?v=${Date.now()}"></video>`;
      return;
    }
    if (artifact.type === "video-set" && (artifact.items || []).length) {
      const items = artifact.items;
      app.selectedCandidate = items[0].n;
      stage.innerHTML = `<span class="stage-badge">Animation candidate</span>
        <video id="candidate-video" controls playsinline preload="metadata" src="${esc(items[0].url)}?v=${Date.now()}"></video>
        <div class="candidate-strip">${items.map((item, index) => `<button type="button" data-candidate="${item.n}" data-url="${esc(item.url)}" class="${index === 0 ? "active" : ""}">C${item.n}</button>`).join("")}</div>`;
      stage.querySelectorAll("[data-candidate]").forEach((button) => button.addEventListener("click", () => {
        app.selectedCandidate = Number(button.dataset.candidate);
        stage.querySelectorAll("[data-candidate]").forEach((item) => item.classList.toggle("active", item === button));
        const video = $("#candidate-video");
        video.src = `${button.dataset.url}?v=${Date.now()}`;
        video.play().catch(() => {});
      }));
      return;
    }
    stage.innerHTML = emptyStage(session.status === "blocked" ? "No result can be built from the current route yet." : "No rendered result yet.", false);
  }

  function actionButton(action, kind) {
    const className = kind === "primary" ? "primary" : `secondary${action.destructive ? " danger" : ""}`;
    const label = action.id.startsWith("accept-") ? "Approve" : action.id.startsWith("iterate-") ? "Refire" : action.label;
    return `<button type="button" class="${className}" data-action="${esc(action.id)}">${esc(label)}</button>`;
  }

  function renderActions(session) {
    const host = $("#action-area");
    if (session.status === "rendering") {
      host.innerHTML = '<button type="button" class="primary" disabled>Working...</button>';
      return;
    }
    if ((session.decisionActions || []).length) {
      host.innerHTML = `<div class="decision-set">${session.decisionActions.map((action, index) => actionButton(action, index === 0 ? "primary" : "secondary")).join("")}</div>`;
    } else if (session.primaryAction) {
      host.innerHTML = actionButton(session.primaryAction, "primary");
    } else {
      host.innerHTML = "";
    }
    host.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => {
      const actions = [session.primaryAction, ...(session.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.action);
      if (action) handleAction(action);
    }));
  }

  function renderDirector(session) {
    $("#scene-kicker").textContent = `Episode 1 · Scene ${session.scene}`;
    $("#director-title").textContent = session.sceneName || `Scene ${session.scene}`;
    $("#phase-label").textContent = phaseLabel(session.phase);
    $("#outcome-headline").textContent = session.headline || "Current decision";
    $("#outcome-summary").textContent = session.summary || "";
    const blocker = $("#blocker-copy");
    blocker.hidden = !session.blocker;
    blocker.textContent = session.blocker?.action || "";
    const quality = $("#quality-copy");
    const review = session.qualityReview || {};
    const reviewText = review.actualRead || review.cheapestNextAction || review.verdict || "";
    quality.hidden = !reviewText;
    quality.textContent = reviewText;
    $("#save-state").textContent = session.lineageCurrent ? "Current" : "Needs refresh";
    $("#references-button").disabled = !session.selectedShotId;
    $("#request-button").disabled = !session.inspector?.providerRequest;
    $("#truth-note").textContent = session.inspector?.structuralClaim || "Creative quality is judged from the result.";
    const inspectorUrl = `/cb-studio/app.html#p=crystal-bears&pg=pipeline&ep=${encodeURIComponent(session.episode)}&sc=${encodeURIComponent(session.scene)}&st=${encodeURIComponent(session.phase)}${session.selectedShotId ? `&shot=${encodeURIComponent(session.selectedShotId)}` : ""}`;
    $("#full-inspector-link").href = inspectorUrl;
    $("#drawer-inspector-link").href = inspectorUrl;
    renderShotSwitcher(session);
    renderArtifact(session);
    renderActions(session);
  }

  function renderEpisodes() {
    const scenes = app.roster?.scenes || [];
    $("#episode-progress-label").textContent = `Scene ${app.scene} in production`;
    $("#episode-progress-bar").style.width = `${Math.max(5, (Number(app.scene) / Math.max(1, scenes.length)) * 100)}%`;
    $("#scene-list").innerHTML = scenes.map((scene) => {
      const number = String(scene.sceneNumber);
      const current = number === app.scene;
      return `<button type="button" class="scene-row ${current ? "current" : ""}" data-scene="${esc(number)}">
        <span class="scene-number">${String(scene.sceneNumber).padStart(2, "0")}</span>
        <span class="scene-copy"><strong>${esc(scene.location || `Scene ${number}`)}</strong><span>${esc(scene.time || "")} · ${scene.beatCount || 0} story beats</span></span>
        <span class="scene-status">${current ? "In production" : "Ready for direction"}</span>
      </button>`;
    }).join("") || '<div class="reference-unavailable">No current scenes.</div>';
    $("#scene-list").querySelectorAll("[data-scene]").forEach((button) => button.addEventListener("click", () => {
      app.scene = button.dataset.scene;
      app.shotId = null;
      app.view = "director";
      setView("director");
      loadSession();
    }));
  }

  function pipelineInspectorHref(step) {
    const stage = {
      upload: "story",
      style: "look",
      analysis: "storyboard",
      characters: "characters",
      props: "props",
      locations: "locations",
      storyboard: "storyboard",
      footage: "animation",
      audio: "voice",
      "rough-cut": "final",
    }[step] || "storyboard";
    return `/cb-studio/app.html#p=crystal-bears&pg=pipeline&ep=${encodeURIComponent(app.episode)}&sc=${encodeURIComponent(app.scene)}&st=${encodeURIComponent(stage)}`;
  }

  function syncPipelineRail() {
    $$("[data-pipeline-step]").forEach((button) => {
      button.classList.toggle("active", button.dataset.pipelineStep === app.pipelineStep);
    });
    const step = pipelineSteps.find((item) => item.id === app.pipelineStep) || pipelineSteps[0];
    const progress = Math.round((step.step / pipelineSteps.length) * 100);
    $("#pipeline-subtitle").textContent = `${step.phase} · Step ${step.step} of ${pipelineSteps.length}`;
    $("#pipeline-progress-copy").textContent = `${progress}%`;
    const bar = $(".pipeline-progress-track i");
    if (bar) bar.style.width = `${progress}%`;
  }

  function renderWardrobe(item) {
    const action = item.state === "regen" ? "Regen" : "Gen";
    return `<article class="wardrobe-card">
      <div class="wardrobe-thumb" aria-hidden="true">${esc(item.initial || item.label.charAt(0))}</div>
      <div class="wardrobe-copy">
        <strong>${esc(item.label)}</strong>
        <span>Scenes ${esc(item.scenes)}</span>
        <em>Nano Banana Pro</em>
      </div>
      <div class="wardrobe-actions">
        <button type="button" disabled>${action}</button>
        <button type="button" disabled>Upload</button>
      </div>
    </article>`;
  }

  function renderCharacterPipeline() {
    const generatedWardrobes = characterRoster.reduce((total, character) => (
      total + character.wardrobes.filter((wardrobe) => wardrobe.state === "regen").length
    ), 0);
    const totalWardrobes = characterRoster.reduce((total, character) => total + character.wardrobes.length, 0);
    return `<div class="pipeline-heading-row">
      <div>
        <h2>Character Portraits</h2>
        <p>${characterRoster.length} characters</p>
      </div>
      <div class="pipeline-metrics">
        <span><strong>${generatedWardrobes}/${totalWardrobes}</strong> wardrobes</span>
        <span><strong>0/${characterRoster.length}</strong> ref sheets</span>
      </div>
      <div class="pipeline-model">Image Model: <strong>Nano Banana Pro</strong></div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" disabled>Add Character</button>
        <button type="button" class="primary" disabled>Generate All · 204 tkn · $2.04</button>
      </div>
    </div>
    <div class="character-stack">
      ${characterRoster.map((character) => `<article class="character-card">
        <div class="character-head">
          <div>
            <h3>${esc(character.name)}</h3>
            <span>${esc(character.scenes)} scenes</span>
          </div>
          <span class="character-state ${character.status}">${character.status === "ready" ? "Asset ready" : "Needs wardrobe"}</span>
        </div>
        <div class="character-grid">
          <section>
            <span class="field-label">Role</span>
            <p>${esc(character.role)}</p>
          </section>
          <section>
            <span class="field-label">Face Identity</span>
            <p>${esc(character.identity)}</p>
          </section>
          <section>
            <span class="field-label">Reference Sheet</span>
            <button type="button" class="secondary compact-control" disabled>${esc(character.reference)}</button>
            <p class="hint">Multi-angle turnaround and face closeups for video consistency.</p>
          </section>
        </div>
        <div class="wardrobe-list">
          <span class="field-label">Wardrobes</span>
          ${character.wardrobes.map(renderWardrobe).join("")}
        </div>
      </article>`).join("")}
      <article class="character-card extras-card">
        <div class="character-head">
          <div>
            <h3>Background Extras</h3>
            <span>1 group</span>
          </div>
          <button type="button" class="secondary compact-control" disabled>Add Group</button>
        </div>
        <span class="field-label">Crystal Bears — Background Group Members</span>
        <p>A group of small anthropomorphic bear characters of varying fur colors, each with a small glowing crystal gem at the chest.</p>
        <div class="pipeline-actions inline">
          <button type="button" class="secondary" disabled>Generate</button>
          <button type="button" class="secondary" disabled>Upload</button>
        </div>
      </article>
    </div>
    <div class="pipeline-footer-actions">
      <a class="secondary" href="${pipelineInspectorHref("characters")}">Open Inspector</a>
      <button type="button" class="primary" data-next-step="props">Continue · Props</button>
    </div>`;
  }

  function renderStylePipeline() {
    return `<div class="pipeline-heading-row">
      <div>
        <h2>Visual Style</h2>
        <p>Choose the visual language applied downstream to characters, locations, storyboard and footage.</p>
      </div>
      <div class="pipeline-model">Current: <strong>3D Animation · 16:9</strong></div>
      <div class="pipeline-actions"><button type="button" class="secondary" disabled>Custom Style</button></div>
    </div>
    <div class="style-stack">
      ${styleFamilies.map((family) => `<section class="option-section">
        <div class="option-section-head"><h3>${esc(family.group)}</h3><span>${family.options.length}</span></div>
        <div class="option-grid">
          ${family.options.map(([name, copy]) => `<button type="button" class="option-card ${name === "3D Animation" ? "selected" : ""}">
            <span class="option-thumb">${esc(name.split(" ").map((part) => part[0]).join("").slice(0, 2))}</span>
            <strong>${esc(name)}</strong>
            <em>${esc(copy)}</em>
          </button>`).join("")}
        </div>
      </section>`).join("")}
      <section class="option-section">
        <div class="option-section-head"><h3>Aspect Ratio</h3><span>6</span></div>
        <div class="aspect-grid">
          ${aspectRatios.map(([ratio, label]) => `<button type="button" class="aspect-card ${ratio === "16:9" ? "selected" : ""}">
            <strong>${esc(ratio)}</strong><span>${esc(label)}</span>
          </button>`).join("")}
        </div>
      </section>
    </div>
    ${renderPipelineFooter("upload", "analysis", "Style")}`;
  }

  function renderAssetGenerationCard(item, index) {
    const [name, scenes, status, prompt] = item;
    const ready = status === "Generated";
    return `<article class="generation-card ${ready ? "approved" : ""}">
      <div class="asset-thumb" aria-hidden="true">${esc(name.charAt(0))}</div>
      <div class="generation-copy">
        <div class="generation-top">
          <div><h3>${esc(name)}</h3><span>Scenes: ${esc(scenes)}</span></div>
          <span class="status-pill ${ready ? "ok" : "idle"}">${esc(status)}</span>
        </div>
        <label>Generation Prompt</label>
        <textarea rows="3" aria-label="${esc(name)} prompt">${esc(prompt)}</textarea>
        <div class="generation-meta"><span>Nano Banana Pro</span><span>${ready ? "Approved" : "AI Gen"}</span><span>${index === 0 ? "17 tkn" : "Queued"}</span></div>
      </div>
      <div class="generation-actions">
        <button type="button" disabled>${ready ? "Regen" : "Generate"}</button>
        <button type="button" disabled>Upload</button>
      </div>
    </article>`;
  }

  function renderPropsPipeline() {
    return `<div class="pipeline-heading-row">
      <div><h2>Props & Key Objects</h2><p>${propRoster.length} props</p></div>
      <div class="pipeline-model">Image Model: <strong>Nano Banana Pro</strong></div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" disabled>Add Prop</button>
        <button type="button" class="primary" disabled>Generate All</button>
      </div>
    </div>
    <div class="generation-stack">${propRoster.map(renderAssetGenerationCard).join("")}</div>
    ${renderPipelineFooter("characters", "locations", "Props")}`;
  }

  function renderLocationCard(location) {
    const [name, mood, scenes, prompt] = location;
    const angles = ["Top-Down", "Wide", "Close-Up", "Low-Angle"];
    return `<article class="location-card">
      <div class="location-head">
        <div><h3>${esc(name)}</h3><span>${esc(mood)} / Scenes: ${esc(scenes)}</span></div>
        <span class="status-pill idle">Draft</span>
      </div>
      <div class="angle-grid">${angles.map((angle) => `<div class="angle-card">
        <span>${esc(angle.charAt(0))}</span><strong>${esc(angle)}</strong><em>GPT Image 2</em>
        <button type="button" disabled>Gen</button>
      </div>`).join("")}</div>
      <label>Generation Prompt</label>
      <textarea rows="4" aria-label="${esc(name)} location prompt">${esc(prompt)}</textarea>
      <div class="pipeline-actions inline">
        <button type="button" class="secondary" disabled>Generate All Angles</button>
        <button type="button" class="secondary" disabled>Upload</button>
      </div>
    </article>`;
  }

  function renderLocationsPipeline() {
    return `<div class="pipeline-heading-row">
      <div><h2>Location Clean Plates</h2><p>${locationRoster.length} locations shown · angle set per location</p></div>
      <div class="pipeline-model">Image Model: <strong>GPT Image 2</strong> <span class="hot">HOT</span></div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" disabled>Rewrite Prompts with AI</button>
        <button type="button" class="primary" disabled>Generate All Locations</button>
      </div>
    </div>
    <div class="location-stack">${locationRoster.map(renderLocationCard).join("")}</div>
    ${renderPipelineFooter("props", "storyboard", "Locations")}`;
  }

  function renderStoryboardShot(shot) {
    return `<article class="storyboard-shot ${shot.status === "Regen" ? "ready" : ""}">
      <div class="storyboard-frame" aria-hidden="true">
        <span>${esc(shot.title)}</span>
        ${shot.characters.map((character) => `<b>${esc(character)}</b>`).join("")}
      </div>
      <div class="storyboard-shot-copy">
        <div class="storyboard-shot-head">
          <strong>Shot ${esc(shot.shot)}</strong>
          <button type="button" class="secondary compact-control" disabled>Edit</button>
        </div>
        ${shot.setup ? `<em>${esc(shot.setup)}</em>` : ""}
        <div class="storyboard-ref-label">References (${shot.refs.length}/6) · ${shot.status === "Regen" ? "Custom · " : ""}Base for generation</div>
        <div class="storyboard-ref-row">${shot.refs.map((ref) => `<span>${esc(ref)}</span>`).join("")}</div>
        <div class="generation-meta"><span>Nano Banana Pro</span><span>${esc(shot.status)} · 17 tkn · $0.17</span></div>
      </div>
    </article>`;
  }

  function renderStoryboardPipeline() {
    return `<div class="pipeline-heading-row">
      <div><h2>Storyboard</h2><p>10 scenes / 126 shots</p></div>
      <div class="pipeline-model">Image Model: <strong>Nano Banana Pro</strong></div>
      <div class="quality-toggle" aria-label="Storyboard quality">
        <button type="button">1K</button><button type="button" class="selected">2K</button><button type="button">4K</button>
      </div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" disabled>Write Prompts with AI</button>
        <button type="button" class="secondary" disabled>Export PDF</button>
        <button type="button" class="primary" disabled>Generate All Scenes · 1,734 tkn · $17.34</button>
      </div>
    </div>
    <div class="scene-board">
      ${sceneRoster.map(([num, title, progress]) => `<button type="button" class="scene-tile ${num === "1" ? "current" : ""}" data-pipeline-scene="${esc(num)}">
        <span>${esc(num)}</span><strong>${esc(title)}</strong><em>${esc(progress)} shots</em>
      </button>`).join("")}
    </div>
    <section class="storyboard-detail">
      <div class="clip-section-head">
        <div><h3>EXT. DEEP WITHIN THE RAINFOREST - DAY</h3><span>16 shots / Fuzzby, Zenny</span></div>
        <div class="pipeline-actions inline">
          <button type="button" class="secondary" disabled>Reset refs</button>
          <button type="button" class="primary" disabled>Generate Scene · 221 tkn · $2.21</button>
        </div>
      </div>
      <div class="storyboard-shot-grid">${storyboardShots.map(renderStoryboardShot).join("")}</div>
    </section>
    ${renderPipelineFooter("locations", "audio", "Storyboard")}`;
  }

  function renderFootagePipeline() {
    return `<div class="pipeline-heading-row">
      <div><h2>Video Clips</h2><p>48 clips · Multi-shot 15s clips</p></div>
      <div class="pipeline-model"><strong>Seedance · 1080p</strong></div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" disabled>Write Prompts with AI</button>
        <button type="button" class="primary" disabled>Generate All Videos · 27,720 tkn · $277.20</button>
      </div>
    </div>
    <div class="jump-row" aria-label="Jump to scene">
      ${sceneRoster.map(([num], index) => `<button type="button" class="${num === "1" ? "selected" : ""}">S${esc(num)} <span>${index === 0 ? "5/6" : index === 1 ? "1/3" : "0/" + (index + 3)}</span></button>`).join("")}
    </div>
    <section class="clip-section">
      <div class="clip-section-head"><h3>Scene 1: EXT. DEEP WITHIN THE RAINFOREST - DAY</h3><span>5/6 clips</span></div>
      ${footageClips.map((clip) => `<article class="clip-card ${clip.state}">
        <div class="clip-card-head">
          <div><h3>${esc(clip.id)} · ${esc(clip.shots)}</h3><span>${esc(clip.count)}</span></div>
          <span class="status-pill ${clip.state === "failed" ? "flagged" : "ok"}">${clip.state === "failed" ? "Failed" : "Ready"}</span>
        </div>
        ${clip.state === "failed" ? '<p class="error-line">Provider rejected this output. Keep the prompt and references for a safer retry.</p>' : ""}
        <div class="start-frame-row"><span>Start frame</span>${(clip.startFrames || []).map((frame) => `<b>${esc(frame)}</b>`).join("")}<button type="button" disabled>Edit frame</button></div>
        <div class="reference-row">${clip.references.map((ref) => `<span>${esc(ref)}</span>`).join("")}<button type="button" disabled>Add reference</button></div>
        <label>Video prompt</label>
        <textarea rows="4" aria-label="${esc(clip.id)} video prompt">${esc(clip.prompt)}</textarea>
        <div class="generation-meta"><span>15s</span><span>Seedance · 1080p</span></div>
        <div class="pipeline-actions inline"><button type="button" class="secondary" disabled>Reset to auto</button><button type="button" class="primary" disabled>${esc(clip.cost)}</button></div>
      </article>`).join("")}
    </section>
    <div class="pipeline-footer-actions">
      <button type="button" class="secondary" data-next-step="audio">Audio</button>
      <button type="button" class="secondary" data-view-jump="director">Open Director</button>
      <button type="button" class="primary" data-next-step="rough-cut">Continue · Rough Cut</button>
    </div>`;
  }

  function renderAudioPipeline() {
    return `<div class="pipeline-heading-row">
      <div><h2>Audio Studio</h2><p>Dialogue extraction, voice selection, VO generation and voice-to-voice repair.</p></div>
      <div class="pipeline-model"><strong>ElevenLabs</strong></div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" disabled>Extract from Script</button>
        <button type="button" class="primary" disabled>Generate All VO</button>
      </div>
    </div>
    <div class="audio-grid">
      <section class="control-panel">
        <span class="field-label">Voice Selection</span>
        <select aria-label="Voice selection"><option>Select character voice</option><option>Fuzzby</option><option>Zenny</option><option>Keen</option></select>
        <button type="button" class="secondary" disabled>Preview Voice</button>
      </section>
      <section class="control-panel">
        <span class="field-label">Voice Settings</span>
        <div class="slider-row"><span>Stability</span><strong>0.50</strong></div>
        <div class="slider-row"><span>Clarity</span><strong>0.75</strong></div>
        <div class="slider-row"><span>Style</span><strong>0.00</strong></div>
      </section>
      <section class="control-panel">
        <span class="field-label">Voice-to-Voice</span>
        <p>Upload any recording and transform it to the selected voice while keeping emotion and pacing.</p>
        <button type="button" class="secondary" disabled>Choose Audio</button>
        <button type="button" class="secondary" disabled>Convert</button>
      </section>
      <section class="control-panel wide">
        <div class="clip-section-head"><h3>Voice-Over Lines</h3><button type="button" class="secondary" disabled>Add Line</button></div>
        <p>No voice-over lines yet. Extract from the locked script or add lines manually.</p>
      </section>
    </div>
    ${renderPipelineFooter("storyboard", "footage", "Audio")}`;
  }

  function renderRoughCutPipeline() {
    return `<div class="pipeline-heading-row">
      <div><h2>Editor</h2><p>6 clips · 1:30.4</p></div>
      <div class="pipeline-actions">
        ${["Split", "Text", "VO", "Music", "Mix", "AI Edit"].map((label) => `<button type="button" class="secondary" disabled>${label}</button>`).join("")}
        <button type="button" class="primary" disabled>Export</button>
      </div>
    </div>
    <div class="editor-grid">
      <aside class="bin-panel"><h3>Bin <span>${editorClips.length}</span></h3>${editorClips.map((clip) => `<button type="button">${esc(clip)}<span>10.0s</span></button>`).join("")}</aside>
      <section class="timeline-panel">
        <div class="preview-window"><span>0:00.0 / 1:30.4</span><strong>S1 C2</strong></div>
        <div class="timeline-ruler">${Array.from({ length: 10 }, (_, index) => `<span>${index * 10}s</span>`).join("")}</div>
        <div class="track"><strong>VIDEO</strong>${editorClips.map((clip) => `<span>${esc(clip)}<em>15.1s</em></span>`).join("")}</div>
        <div class="track muted"><strong>TEXT</strong><button type="button" disabled>Add text</button></div>
        <div class="track muted"><strong>AUDIO</strong><span>No VO</span><span>No music</span></div>
      </section>
      <aside class="shortcut-panel"><h3>Shortcuts</h3><p>Space Play/Pause · J/K/L Prev/Play/Next · S Split · T Add Text · Cmd+Z Undo</p></aside>
    </div>
    <div class="pipeline-footer-actions">
      <button type="button" class="secondary" data-next-step="footage">Footage</button>
      <a class="secondary" href="${pipelineInspectorHref("rough-cut")}">Open Inspector</a>
      <button type="button" class="primary" disabled>Finish & Export</button>
    </div>`;
  }

  function renderPipelineFooter(previous, next, label) {
    return `<div class="pipeline-footer-actions">
      <button type="button" class="secondary" data-next-step="${esc(previous)}">Back</button>
      <a class="secondary" href="${pipelineInspectorHref(label.toLowerCase())}">Open Inspector</a>
      <button type="button" class="primary" data-next-step="${esc(next)}">Continue · ${esc((pipelineSteps.find((step) => step.id === next) || {}).label || "Next")}</button>
    </div>`;
  }

  function renderStepPlaceholder(step) {
    if (step.id === "style") return renderStylePipeline();
    if (step.id === "props") return renderPropsPipeline();
    if (step.id === "locations") return renderLocationsPipeline();
    if (step.id === "storyboard") return renderStoryboardPipeline();
    if (step.id === "footage") return renderFootagePipeline();
    if (step.id === "audio") return renderAudioPipeline();
    if (step.id === "rough-cut") return renderRoughCutPipeline();
    const details = {
      upload: ["Brief & Script", "Script intake is locked from the current EP1 source. This step owns logline, treatment, script and shot-list source material."],
      analysis: ["Analysis", "Analysis is derived from approved intake and lineage. It activates only when the script step is current and approved."],
    }[step.id] || [step.label, "This production step is available in the full Inspector."];
    return `<div class="step-placeholder">
      <span class="stage-label">${esc(step.phase)} · Step ${step.step} of 10</span>
      <h2>${esc(details[0])}</h2>
      <p>${esc(details[1])}</p>
      <div class="pipeline-actions inline">
        <a class="primary" href="${pipelineInspectorHref(step.id)}">Open this step</a>
        ${step.id === "footage" ? '<button type="button" class="secondary" data-view-jump="director">Open Director</button>' : ""}
      </div>
    </div>`;
  }

  function livePipelineStep(session) {
    return {
      story: "analysis",
      keyframe: "storyboard",
      voice: "audio",
      animation: "footage",
      review: "rough-cut",
      final: "rough-cut",
    }[session?.phase] || "upload";
  }

  function renderTruthRail() {
    const host = $("#truth-rail");
    if (!host) return;
    const session = app.session || {};
    const progress = session.progress || {};
    const truth = [
      ["Canon", session.lineageCurrent ? "Proven" : "Blocked", session.lineageCurrent ? "proven" : "blocked"],
      ["Script", session.episode ? "Locked" : "Awaiting", session.episode ? "proven" : "awaiting"],
      ["Assets", session.selectedShotId ? "Built" : "Proposed", session.selectedShotId ? "built" : "proposed"],
      ["Shots", `${progress.complete || 0}/${progress.total || 0} approved`, (progress.complete || 0) === (progress.total || -1) ? "proven" : "awaiting"],
      ["Spend", session.primaryAction?.paid ? "Approval required" : "Protected", session.primaryAction?.paid ? "awaiting" : "proven"],
      ["Delivery", session.phase === "final" ? "Ready" : "Not ready", session.phase === "final" ? "proven" : "locked"],
    ];
    host.innerHTML = truth.map(([label, value, state]) => `<div class="truth-chip ${state}"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
  }

  function pipelineStepState(step, session) {
    const phase = session?.phase;
    const completed = new Set();
    let current = livePipelineStep(session);
    let blockedReason = "Complete the current production step first.";
    if (phase === "story") {
      ["upload", "style"].forEach((id) => completed.add(id));
    } else if (phase === "keyframe") {
      ["upload", "style", "analysis", "characters", "props", "locations"].forEach((id) => completed.add(id));
    } else if (phase === "voice") {
      ["upload", "style", "analysis", "characters", "props", "locations", "storyboard"].forEach((id) => completed.add(id));
      if (step.id === "footage") blockedReason = "Approve the audio performances before generating footage.";
    } else if (phase === "animation") {
      ["upload", "style", "analysis", "characters", "props", "locations", "storyboard", "audio"].forEach((id) => completed.add(id));
    } else if (phase === "review") {
      pipelineSteps.filter((item) => item.id !== "rough-cut").forEach((item) => completed.add(item.id));
    } else if (phase === "final") {
      pipelineSteps.forEach((item) => completed.add(item.id));
      current = null;
    }
    if (completed.has(step.id)) return { kind: "completed", label: "Completed", reason: "Approved production evidence is available." };
    if (step.id === current) {
      if (session?.status === "blocked") return { kind: "blocked", label: "Blocked", reason: session.blocker?.action || "Resolve the current blocker." };
      return { kind: "current", label: "Current step", reason: session?.summary || "Ready for the next production action." };
    }
    const isFootageWaitingForAudio = phase === "voice" && step.id === "footage";
    return { kind: isFootageWaitingForAudio ? "blocked" : "locked", label: isFootageWaitingForAudio ? "Blocked" : "Locked", reason: blockedReason };
  }

  function renderVoicePerformanceDesk(availableActions) {
    const expectedKey = app.session?.selectedShotId
      ? `${app.session.episode}:${app.session.scene}:${app.session.selectedShotId}`
      : null;
    if (app.voiceStatusKey !== expectedKey || (app.voiceLoading && !app.voiceStatus)) {
      return '<section class="voice-desk"><div class="voice-desk-loading">Loading the ElevenLabs performance prompt...</div></section>';
    }
    const status = app.voiceStatus || {};
    if (status.error) {
      return `<section class="voice-desk"><div class="voice-desk-loading error-line">${esc(status.error)}</div></section>`;
    }
    const lines = status.currentLines || [];
    const approved = status.approvedLines || [];
    const acceptAction = availableActions.find((action) => action.id.startsWith("accept-"));
    const iterateAction = availableActions.find((action) => action.id.startsWith("iterate-"));
    const sendAction = availableActions.find((action) =>
      !action.id.startsWith("accept-") && !action.id.startsWith("iterate-") &&
      /voice|performance/i.test(`${action.id} ${action.label}`));
    const sourceLabel = {
      "human-working": "Edited working prompt",
      "voice-director-approved": "Director-approved prompt",
      "legacy-approved-storyboard": "Approved script performance",
    }[status.source] || "ElevenLabs prompt";
    const selectedShot = (app.session?.shots || []).find((shot) => shot.selected) || (app.session?.shots || [])[0];
    const take = app.session?.artifact?.type === "audio" ? app.session.artifact : null;
    return `<section class="voice-desk">
      <div class="voice-desk-head">
        <div><span class="stage-label">ELEVENLABS PERFORMANCE · ${esc(selectedShot?.shotId || app.shotId || "CURRENT SHOT")}${selectedShot?.durationSec ? ` · ${Number(selectedShot.durationSec)}s` : ""}</span><h3>Acting &amp; cadence prompt</h3></div>
        <span class="voice-source ${status.isWorking ? "working" : ""}">${esc(sourceLabel)}</span>
      </div>
      ${take?.url ? `<div class="voice-take-player">
        <div><span>Generated performance</span><strong>${esc(take.label || "Current take")}</strong>${status.takeGeneratedAt ? `<em>${esc(status.takeGeneratedAt)}</em>` : ""}</div>
        <audio controls preload="metadata" src="${esc(take.url)}?v=${Date.now()}"></audio>
      </div>` : ""}
      <div class="voice-prompt-lines">
        ${lines.map((line, index) => {
          const truth = approved[index] || {};
          return `<article class="voice-prompt-line">
            <div class="voice-line-head"><strong>${esc(line.speaker)}</strong><span>Line ${index + 1}</span></div>
            <div class="locked-dialogue"><span>Exact script</span><p>${esc(truth.exactText || line.text)}</p></div>
            <div class="voice-direction-grid">
              <div><span>Acting intention</span><p>${esc(line.dramaticIntention || "-")}</p></div>
              <div><span>Subtext</span><p>${esc(line.subtext || "-")}</p></div>
              <div><span>Cadence &amp; breath</span><p>${esc(line.cadenceAndBreath || "-")}</p></div>
              <div><span>Timing &amp; body</span><p>${esc(line.timingAndBody || "-")}</p></div>
            </div>
            <label for="voice-line-${index}">Text + audio tags sent to ElevenLabs</label>
            <textarea id="voice-line-${index}" rows="3" data-voice-line="${index}" aria-label="${esc(line.speaker)} line ${index + 1} text and audio tags sent to ElevenLabs">${esc(line.text)}</textarea>
          </article>`;
        }).join("") || '<div class="voice-desk-loading">This shot has no dialogue.</div>'}
      </div>
      ${lines.length ? `<div class="voice-desk-actions">
        <button type="button" class="secondary" data-voice-restore ${status.isWorking ? "" : "disabled"}>Restore director prompt</button>
        <button type="button" class="secondary" data-voice-save>Save changes</button>
        ${iterateAction ? `<button type="button" class="secondary danger" data-live-action="${esc(iterateAction.id)}">Refire</button>` : ""}
        ${acceptAction ? `<button type="button" class="secondary" data-live-action="${esc(acceptAction.id)}">Approve</button>` : ""}
        ${acceptAction ? `<button type="button" class="primary" data-live-action="${esc(acceptAction.id)}" data-advance-step="footage">Approve &amp; Continue</button>` : ""}
        ${sendAction ? `<button type="button" class="primary" data-voice-send="${esc(sendAction.id)}">Send to ElevenLabs</button>` : ""}
      </div>` : ""}
    </section>`;
  }

  async function loadVoicePerformance(force = false) {
    const session = app.session;
    if (!session?.selectedShotId) return;
    const key = `${session.episode}:${session.scene}:${session.selectedShotId}`;
    if (!force && (app.voiceLoading || app.voiceStatusKey === key)) return;
    app.voiceLoading = true;
    app.voiceStatusKey = key;
    if (app.pipelineStep === "audio") renderPipeline();
    try {
      app.voiceStatus = await api(`/api/shot-voice-status?episode=${encodeURIComponent(session.episode)}&scene=${encodeURIComponent(session.scene)}&shotId=${encodeURIComponent(session.selectedShotId)}`);
    } catch (error) {
      app.voiceStatus = { error: error.message };
    } finally {
      app.voiceLoading = false;
      if (app.pipelineStep === "audio") renderPipeline();
    }
  }

  function voiceLinesFromEditor() {
    const current = app.voiceStatus?.currentLines || [];
    return $$('[data-voice-line]').map((field) => {
      const line = current[Number(field.dataset.voiceLine)] || {};
      return {
        dialogueOccurrenceId: line.dialogueOccurrenceId,
        sourceEventId: line.sourceEventId,
        speaker: line.speaker,
        text: field.value.trim(),
      };
    });
  }

  async function saveVoicePerformance(silent = false) {
    if (!app.session?.selectedShotId) return false;
    const lines = voiceLinesFromEditor();
    if (!lines.length || lines.some((line) => !line.text)) {
      toast("Every performance line needs text.", true);
      return false;
    }
    try {
      await api("/api/shot-voice-save", {
        method: "POST",
        body: JSON.stringify({
          episode: app.session.episode,
          scene: app.session.scene,
          shotId: app.session.selectedShotId,
          lines,
        }),
      });
      await loadVoicePerformance(true);
      if (!silent) toast("ElevenLabs prompt saved. Nothing was generated.");
      return true;
    } catch (error) {
      toast(error.message, true);
      return false;
    }
  }

  async function restoreVoicePerformance() {
    if (!app.session?.selectedShotId || !window.confirm("Restore the director-approved ElevenLabs prompt?")) return;
    try {
      await api("/api/shot-voice-restore", {
        method: "POST",
        body: JSON.stringify({
          episode: app.session.episode,
          scene: app.session.scene,
          shotId: app.session.selectedShotId,
        }),
      });
      await loadVoicePerformance(true);
      toast("Director prompt restored. Nothing was generated.");
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function sendVoicePerformance(action) {
    if (!await saveVoicePerformance(true)) return;
    handleAction(action);
  }

  function renderRoughCutDesk() {
    if (app.roughCutStatusKey !== app.episode || (app.roughCutLoading && !app.roughCutStatus)) {
      return '<section class="rough-cut-desk"><div class="voice-desk-loading">Loading approved episode footage...</div></section>';
    }
    const status = app.roughCutStatus || {};
    if (status.error) {
      return `<section class="rough-cut-desk"><p class="pipeline-blocker">${esc(status.error)}</p></section>`;
    }
    const sequence = status.sequence || [];
    const available = status.available || [];
    const totalDuration = sequence.filter((shot) => shot.current).reduce((total, shot) => total + Number(shot.durationSec || 0), 0);
    return `<section class="rough-cut-desk">
      <div class="rough-cut-head">
        <div><span class="stage-label">EPISODE EDIT DECISION LIST</span><h3>Rough-cut sequence</h3><p>${sequence.length} shots · ${Math.round(totalDuration)}s · saved automatically</p></div>
        <span class="voice-source ${status.staleCount ? "working" : ""}">${status.staleCount ? `${status.staleCount} source ${status.staleCount === 1 ? "needs" : "need"} attention` : "Sources current"}</span>
      </div>
      <div class="rough-cut-layout">
        <div class="rough-cut-sequence">
          <h4>Cut order</h4>
          ${sequence.map((shot) => `<article class="rough-cut-shot ${shot.current ? "" : "stale"}">
            <span class="rough-cut-order">${Number(shot.order)}</span>
            <div><strong>${esc(shot.shotId)}</strong><span>Scene ${esc(shot.scene)}${shot.durationSec ? ` · ${Number(shot.durationSec)}s` : ""}</span>${shot.reason ? `<em>${esc(shot.reason)}</em>` : ""}</div>
            <button type="button" class="icon-action" data-rough-remove="${esc(shot.shotId)}" aria-label="Remove ${esc(shot.shotId)} from rough cut" title="Remove shot">×</button>
          </article>`).join("") || '<div class="rough-cut-empty"><strong>No shots in the cut yet</strong><span>Add an approved take from the shot bin.</span></div>'}
        </div>
        <div class="rough-cut-bin">
          <h4>Approved shot bin</h4>
          ${available.map((shot) => `<article class="rough-cut-bin-shot ${shot.inCut ? "in-cut" : ""}">
            ${shot.url ? `<video controls playsinline preload="metadata" src="${esc(shot.url)}"></video>` : '<div class="rough-cut-thumb">Approved</div>'}
            <div><strong>${esc(shot.shotId)}</strong><span>Scene ${esc(shot.scene)}${shot.durationSec ? ` · ${Number(shot.durationSec)}s` : ""}</span><p>${esc(shot.purpose || "")}</p></div>
            <button type="button" class="${shot.inCut ? "secondary" : "primary"}" data-rough-add="${esc(shot.shotId)}" ${shot.inCut ? "disabled" : ""}>${shot.inCut ? "In cut" : "Add shot"}</button>
          </article>`).join("") || '<div class="rough-cut-empty"><strong>No approved footage yet</strong><span>Accepted animation takes will appear here automatically.</span></div>'}
        </div>
      </div>
    </section>`;
  }

  async function loadRoughCut(force = false) {
    if (!force && (app.roughCutLoading || app.roughCutStatusKey === app.episode)) return;
    app.roughCutLoading = true;
    app.roughCutStatusKey = app.episode;
    if (app.pipelineStep === "rough-cut") renderPipeline();
    try {
      app.roughCutStatus = await api(`/api/rough-cut-draft?episode=${encodeURIComponent(app.episode)}`);
    } catch (error) {
      app.roughCutStatus = { error: error.message };
    } finally {
      app.roughCutLoading = false;
      if (app.pipelineStep === "rough-cut") renderPipeline();
    }
  }

  async function updateRoughCut(action, shotId) {
    try {
      app.roughCutStatus = await api("/api/rough-cut-draft", {
        method: "POST",
        body: JSON.stringify({ episode: app.episode, action, shotId }),
      });
      app.roughCutStatusKey = app.episode;
      renderPipeline();
      toast(action === "add" ? `${shotId} added to the rough cut.` : `${shotId} removed from the rough cut.`);
    } catch (error) {
      toast(error.message, true);
    }
  }

  function renderCanonicalPipelineStep(step) {
    const details = {
      upload: ["Brief & script", "Import and lock the screenplay that governs every scene, line and story beat."],
      style: ["Visual style", "Lock the Crystal Bears 3D CGI profile, frame format and provider-safe visual language before paid downstream work."],
      analysis: ["Story & direction", "Turn the locked script into cinematic scenes and performance-led shots with humour, emotion and clear visual storytelling."],
      characters: ["Character assets", "Bind every character to approved turnarounds, structured identity traits, wardrobe, expressions and scene coverage."],
      props: ["Props & key objects", "Track canonical appearance, ownership, scene usage, allowed variations and approval for every story-critical object."],
      locations: ["Location clean plates", "Keep approved world plates, camera angles, light, weather and emotional state separate from story performance frames."],
      storyboard: ["Storyboard & keyframes", "Package direction into natural 15-30 second shots, attach explained references, and approve the keyframe as the visual truth."],
      footage: ["Footage", "Animate approved keyframes through the verified Seedance route, then review picture, lip sync, duration, drift and continuity separately."],
      audio: ["Audio performances", "Protect exact script lines while generating, repairing and approving character performances at line level."],
      "rough-cut": ["Rough cut & master", "Stitch accepted shots, expose missing media, complete edit, sound, score and colour, then pass the final delivery checklist."],
    }[step.id];
    const session = app.session || {};
    const liveStep = livePipelineStep(session);
    const index = pipelineSteps.findIndex((item) => item.id === step.id);
    const stepState = pipelineStepState(step, session);
    const selectedShot = (session.shots || []).find((shot) => shot.selected) || (session.shots || [])[0];
    const artifact = session.artifact || {};
    const showArtifact = ["storyboard", "footage", "rough-cut"].includes(step.id) && artifact.url;
    const previous = pipelineSteps[index - 1];
    const next = pipelineSteps[index + 1];
    const availableActions = [session.primaryAction, ...(session.decisionActions || [])].filter(Boolean);
    const acceptAction = availableActions.find((action) => action.id.startsWith("accept-"));
    const iterateAction = availableActions.find((action) => action.id.startsWith("iterate-"));
    const otherActions = availableActions.filter((action) => action !== acceptAction && action !== iterateAction);
    const voiceDesk = step.id === "audio" ? renderVoicePerformanceDesk(availableActions) : "";
    const roughCutDesk = step.id === "rough-cut" ? renderRoughCutDesk() : "";
    const liveActionButtons = [
      acceptAction && `<button type="button" class="secondary" data-live-action="${esc(acceptAction.id)}">Approve</button>`,
      iterateAction && `<button type="button" class="secondary danger" data-live-action="${esc(iterateAction.id)}">Refire</button>`,
      acceptAction && next && `<button type="button" class="primary" data-live-action="${esc(acceptAction.id)}" data-advance-step="${esc(next.id)}">Approve &amp; Continue</button>`,
      ...otherActions.map((action, actionIndex) => `<button type="button" class="${actionIndex === 0 ? "primary" : "secondary"}${action.destructive ? " danger" : ""}" data-live-action="${esc(action.id)}">${esc(action.label)}</button>`),
    ].filter(Boolean).join("");
    let workflowActions = "";
    if (stepState.kind === "current") {
      workflowActions = step.id === "audio" ? "" : `${liveActionButtons || '<button type="button" class="primary" data-view-jump="director">Open current scene</button>'}
          <button type="button" class="secondary" data-open-references>References</button>
          <button type="button" class="secondary" data-open-request>Exact request</button>`;
    } else if (stepState.kind === "completed") {
      workflowActions = `${next ? `<button type="button" class="primary" data-next-step="${esc(next.id)}">Continue · ${esc(next.label)}</button>` : '<button type="button" class="primary" data-view-jump="review">Open master</button>'}`;
    } else {
      workflowActions = `<button type="button" class="primary" data-jump-current="${esc(liveStep)}">Return to ${esc((pipelineSteps.find((item) => item.id === liveStep) || {}).label || "current step")}</button>`;
    }
    return `<section class="canonical-step">
      <div class="canonical-step-heading">
        <div>
          <span class="stage-label">${esc(step.phase)} · ${step.step} of ${pipelineSteps.length}</span>
          <h2>${esc(details[0])}</h2>
          <p>${esc(details[1])}</p>
        </div>
        <span class="live-badge ${stepState.kind}">${esc(stepState.label)}</span>
      </div>
      ${renderProductionNavigator(step)}
      ${showArtifact ? `<div class="pipeline-artifact"><img src="${esc(artifact.url)}?v=${Date.now()}" alt="${esc(artifact.label || "Current production result")}"><span>${esc(artifact.label || "Current result")}</span></div>` : ""}
      ${step.id === "audio" ? "" : `<div class="production-now">
        <div><span>Current scene</span><strong>${esc(session.sceneName || `Scene ${app.scene}`)}</strong></div>
        <div><span>Current shot</span><strong>${esc(selectedShot?.shotId || app.shotId || "Select in Director")}${selectedShot?.durationSec ? ` · ${Number(selectedShot.durationSec)}s` : ""}</strong></div>
        <div><span>Outcome</span><strong>${esc(session.headline || "Ready for production")}</strong></div>
      </div>`}
      ${voiceDesk}
      ${roughCutDesk}
      ${stepState.kind === "blocked" || stepState.kind === "locked" ? `<p class="pipeline-blocker">${esc(stepState.reason)}</p>` : ""}
      <div class="canonical-actions">
        <button type="button" class="text-button" data-open-evidence="${esc(step.id)}">Evidence</button>
        <div>
          ${previous ? `<button type="button" class="secondary" data-next-step="${esc(previous.id)}">Back</button>` : ""}
          ${workflowActions}
        </div>
      </div>
    </section>`;
  }

  function renderPipeline() {
    syncPipelineRail();
    renderTruthRail();
    const step = pipelineSteps.find((item) => item.id === app.pipelineStep) || pipelineSteps[0];
    const panel = $("#pipeline-panel");
    if (!panel) return;
    panel.innerHTML = renderCanonicalPipelineStep(step);
    panel.querySelectorAll("[data-next-step]").forEach((button) => button.addEventListener("click", () => {
      app.pipelineStep = button.dataset.nextStep;
      writeHash();
      renderPipeline();
    }));
    panel.querySelectorAll("[data-view-jump]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.viewJump)));
    panel.querySelectorAll("[data-jump-current]").forEach((button) => button.addEventListener("click", () => {
      app.pipelineStep = button.dataset.jumpCurrent;
      writeHash();
      renderPipeline();
    }));
    panel.querySelectorAll("[data-production-scene]").forEach((button) => button.addEventListener("click", () => {
      if (button.dataset.productionScene === app.scene) return;
      app.scene = button.dataset.productionScene;
      app.shotId = null;
      resetShotScopedState();
      writeHash();
      loadSession();
    }));
    panel.querySelectorAll("[data-production-shot]").forEach((button) => button.addEventListener("click", () => {
      if (button.dataset.productionShot === app.shotId) return;
      app.shotId = button.dataset.productionShot;
      resetShotScopedState();
      writeHash();
      loadSession();
    }));
    panel.querySelectorAll("[data-live-action]").forEach((button) => button.addEventListener("click", () => {
      const actions = [app.session?.primaryAction, ...(app.session?.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.liveAction);
      if (!action) return;
      if (button.dataset.advanceStep) {
        app.pendingAdvance = {
          step: button.dataset.advanceStep,
          actionId: action.id,
          phase: app.session?.phase,
        };
      }
      handleAction(action);
    }));
    panel.querySelectorAll("[data-open-evidence]").forEach((button) => button.addEventListener("click", () => openEvidence(button.dataset.openEvidence)));
    panel.querySelectorAll("[data-open-references]").forEach((button) => button.addEventListener("click", openReferences));
    panel.querySelectorAll("[data-open-request]").forEach((button) => button.addEventListener("click", openRequest));
    panel.querySelectorAll("[data-voice-save]").forEach((button) => button.addEventListener("click", () => saveVoicePerformance()));
    panel.querySelectorAll("[data-voice-restore]").forEach((button) => button.addEventListener("click", restoreVoicePerformance));
    panel.querySelectorAll("[data-voice-send]").forEach((button) => button.addEventListener("click", () => {
      const actions = [app.session?.primaryAction, ...(app.session?.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.voiceSend);
      if (action) sendVoicePerformance(action);
    }));
    panel.querySelectorAll("[data-rough-add]").forEach((button) => button.addEventListener("click", () => updateRoughCut("add", button.dataset.roughAdd)));
    panel.querySelectorAll("[data-rough-remove]").forEach((button) => button.addEventListener("click", () => updateRoughCut("remove", button.dataset.roughRemove)));
    if (step.id === "audio") loadVoicePerformance();
    if (step.id === "rough-cut") loadRoughCut();
  }

  function renderReview(session) {
    const shots = session.shots || [];
    $("#review-count").textContent = `${session.progress?.complete || 0} of ${session.progress?.total || 0} shots accepted`;
    $("#review-reel").innerHTML = shots.map((shot) => `
      <div class="review-shot">
        ${shot.acceptedUrl ? `<video controls playsinline preload="metadata" src="${esc(shot.acceptedUrl)}"></video>` : `<div class="review-placeholder">${shot.state === "complete" ? "Accepted take unavailable" : "No accepted take"}</div>`}
        <div class="review-copy"><h3>Shot ${shot.number}${shot.durationSec ? ` · ${Number(shot.durationSec)} seconds` : ""}</h3><p>${esc(shot.purpose || "")}</p></div>
        <span class="review-state ${shot.state === "complete" ? "complete" : ""}">${shot.state === "complete" ? "Accepted" : statusText(shot.state)}</span>
      </div>`).join("") || '<div class="reference-unavailable">No production shots yet.</div>';
    const allAccepted = shots.length > 0 && shots.every((shot) => shot.state === "complete");
    $("#master-band").innerHTML = `<div><span class="stage-label">FINAL MASTER</span><h2>${allAccepted ? "Ready for quality review" : "Waiting for accepted animation"}</h2></div><span class="master-status">${allAccepted ? "Next" : "Not ready"}</span>`;
  }

  async function loadRoster() {
    try {
      app.roster = await api(`/api/scene-roster?episode=${encodeURIComponent(app.episode)}`);
      renderEpisodes();
    } catch (error) {
      $("#scene-list").innerHTML = `<div class="reference-unavailable">${esc(error.message)}</div>`;
    }
  }

  async function loadSession() {
    clearTimeout(app.pollTimer);
    const shot = app.shotId ? `&shotId=${encodeURIComponent(app.shotId)}` : "";
    try {
      const session = await api(`/api/director-session?episode=${encodeURIComponent(app.episode)}&scene=${encodeURIComponent(app.scene)}${shot}`);
      app.session = session;
      app.shotId = session.selectedShotId || app.shotId;
      let approvedAdvance = false;
      if (app.pendingAdvance && session.status !== "rendering") {
        const actionIds = [session.primaryAction, ...(session.decisionActions || [])]
          .filter(Boolean)
          .map((action) => action.id);
        if (!actionIds.includes(app.pendingAdvance.actionId)) {
          app.pipelineStep = app.pendingAdvance.step;
          app.pendingAdvance = null;
          app.view = "pipeline";
          approvedAdvance = true;
        }
      }
      writeHash();
      renderDirector(session);
      renderReview(session);
      if (app.view === "pipeline") renderPipeline();
      if (approvedAdvance) toast("Approved. Moving forward.");
      if (session.status === "rendering") app.pollTimer = setTimeout(loadSession, 1600);
    } catch (error) {
      $("#media-stage").innerHTML = emptyStage(error.message, false);
      $("#outcome-headline").textContent = "Director state unavailable";
      $("#outcome-summary").textContent = error.message;
      $("#action-area").innerHTML = '<a class="secondary" href="/cb-studio/app.html">Open Inspector</a>';
      toast(error.message, true);
    }
  }

  function openConfirmation(action) {
    app.pendingAction = action;
    const spend = app.session?.spendDisclosure;
    $("#confirm-title").textContent = action.label;
    $("#confirm-copy").textContent = action.id === "approve-spend"
      ? "The exact request, references, duration, model and maximum cost are sealed."
      : "This creates a new result through the current production provider. Existing accepted work remains protected.";
    const cost = $("#confirm-cost");
    if (spend?.maxBatchCostUsd != null) {
      cost.hidden = false;
      cost.textContent = `Maximum provider cost: $${Number(spend.maxBatchCostUsd).toFixed(2)} · ${spend.candidateCount || 1} candidate${spend.candidateCount === 1 ? "" : "s"}`;
    } else {
      cost.hidden = true;
      cost.textContent = "";
    }
    $("#confirm-submit").textContent = action.id === "approve-spend" ? "Render" : "Continue";
    $("#confirm-dialog").showModal();
  }

  function openIteration(action) {
    app.pendingAction = action;
    $("#iteration-note").value = "";
    $("#iterate-dialog").showModal();
    setTimeout(() => $("#iteration-note").focus(), 30);
  }

  async function handleAction(action) {
    if (action.id === "cancel-spend") {
      toast("Nothing spent. The sealed request remains available.");
      return;
    }
    if (action.id.startsWith("iterate-")) {
      openIteration(action);
      return;
    }
    if (action.paid) {
      openConfirmation(action);
      return;
    }
    await submitAction(action);
  }

  async function submitAction(action, note) {
    if (!app.session) return;
    $$("#action-area button").forEach((button) => { button.disabled = true; });
    try {
      const result = await api("/api/director-action", {
        method: "POST",
        body: JSON.stringify({
          episode: app.session.episode,
          scene: app.session.scene,
          shotId: app.session.selectedShotId,
          action: action.id,
          note: note || "",
          candidate: app.selectedCandidate,
        }),
      });
      if (result.navigate) {
        location.href = result.navigate;
        return;
      }
      toast(result.noChange ? "Nothing changed." : "Director action started.");
      setTimeout(loadSession, 350);
    } catch (error) {
      app.pendingAdvance = null;
      if (error.payload?.session) {
        app.session = error.payload.session;
        renderDirector(app.session);
      }
      toast(error.message, true);
      $$("#action-area button").forEach((button) => { button.disabled = false; });
    }
  }

  async function openReferences() {
    if (!app.session?.selectedShotId) return;
    $("#reference-grid").innerHTML = '<div class="reference-unavailable">Loading references...</div>';
    $("#reference-dialog").showModal();
    try {
      app.references = await api(`/api/shot-references?episode=${encodeURIComponent(app.session.episode)}&scene=${encodeURIComponent(app.session.scene)}&shotId=${encodeURIComponent(app.session.selectedShotId)}`);
      renderReferences();
    } catch (error) {
      $("#reference-grid").innerHTML = `<div class="reference-unavailable">${esc(error.message)}</div>`;
    }
  }

  function renderReferences() {
    $$('[data-reference-stage]').forEach((button) => button.classList.toggle("active", button.dataset.referenceStage === app.referenceStage));
    const stage = app.references?.[app.referenceStage] || {};
    const references = stage.references || [];
    $("#reference-grid").innerHTML = references.map((item) => `
      <div class="reference-item">
        ${item.url ? `<img src="${esc(item.url)}" alt="${esc(item.role || item.label || "Production reference")}">` : '<div class="review-placeholder">Unavailable</div>'}
        <strong>${esc(item.role || item.label || item.slot || "Reference")}</strong>
        <span>${esc(item.identity?.intactTurnaround
          ? "Complete uncropped 360 turnaround · locked"
          : item.message || item.status || "Locked")}</span>
      </div>`).join("") || '<div class="reference-unavailable">No references are required for this stage.</div>';
  }

  function openEvidence(stepId) {
    const step = pipelineSteps.find((item) => item.id === stepId) || pipelineSteps[0];
    const session = app.session || {};
    const state = pipelineStepState(step, session);
    const shot = (session.shots || []).find((item) => item.selected) || (session.shots || [])[0];
    $("#request-title").textContent = `${step.label} evidence`;
    $("#request-meta").innerHTML = `<span>${esc(state.label)}</span><span>${esc(session.episode || app.episode)}</span><span>${esc(shot?.shotId || app.shotId || "No shot")}</span>`;
    $("#request-content").textContent = [
      `Stage: ${step.label}`,
      `State: ${state.label}`,
      `Scene: ${session.sceneName || `Scene ${app.scene}`}`,
      `Shot: ${shot?.shotId || app.shotId || "Not selected"}${shot?.durationSec ? ` · ${Number(shot.durationSec)}s` : ""}`,
      `Outcome: ${session.headline || "No production outcome yet"}`,
      `Authority: ${session.inspector?.structuralClaim || "Current Studio state"}`,
      `Reason: ${state.reason}`,
    ].join("\n\n");
    $("#drawer-inspector-link").href = pipelineInspectorHref(step.id);
    $("#request-drawer").classList.add("open");
    $("#request-drawer").setAttribute("aria-hidden", "false");
    $("#drawer-scrim").hidden = false;
  }

  function openRequest() {
    const request = app.session?.inspector?.providerRequest;
    if (!request) return;
    $("#request-title").textContent = "Exact provider request";
    const content = request.prompt || (request.lines || []).map((line) => `${line.speaker}: ${line.performedText}`).join("\n");
    $("#request-content").textContent = content || "No provider text is required for this step.";
    $("#request-meta").innerHTML = [
      request.kind && `<span>${esc(request.kind)}</span>`,
      request.source && `<span>${esc(request.source)}</span>`,
      request.promptHash && `<span>${esc(request.promptHash.slice(0, 12))}</span>`,
      app.session.providerModel && request.kind === "animation" && `<span>${esc(app.session.providerModel)}</span>`,
    ].filter(Boolean).join("");
    $("#request-drawer").classList.add("open");
    $("#request-drawer").setAttribute("aria-hidden", "false");
    $("#drawer-scrim").hidden = false;
  }

  function closeRequest() {
    $("#request-drawer").classList.remove("open");
    $("#request-drawer").setAttribute("aria-hidden", "true");
    $("#drawer-scrim").hidden = true;
  }

  function bindEvents() {
    $$('[data-view]').forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
    $$("[data-pipeline-step]").forEach((button) => button.addEventListener("click", () => {
      if (button.disabled) return;
      app.pipelineStep = button.dataset.pipelineStep;
      app.view = "pipeline";
      setView("pipeline");
    }));
    $("#continue-directing").addEventListener("click", () => setView("director"));
    $("#references-button").addEventListener("click", openReferences);
    $("#request-button").addEventListener("click", openRequest);
    $("#request-close").addEventListener("click", closeRequest);
    $("#drawer-scrim").addEventListener("click", closeRequest);
    $$('[data-close]').forEach((button) => button.addEventListener("click", () => {
      const dialog = document.getElementById(button.dataset.close);
      if (dialog?.open) dialog.close();
      if (button.dataset.close === "confirm-dialog") {
        app.pendingAction = null;
        app.pendingAdvance = null;
      }
    }));
    $("#confirm-dialog").addEventListener("cancel", () => {
      app.pendingAction = null;
      app.pendingAdvance = null;
    });
    $$('[data-reference-stage]').forEach((button) => button.addEventListener("click", () => {
      app.referenceStage = button.dataset.referenceStage;
      renderReferences();
    }));
    $("#iterate-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const note = $("#iteration-note").value.trim();
      if (!note || !app.pendingAction) return;
      $("#iterate-dialog").close();
      const action = app.pendingAction;
      app.pendingAction = null;
      await submitAction(action, note);
    });
    $("#confirm-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!app.pendingAction) return;
      $("#confirm-dialog").close();
      const action = app.pendingAction;
      app.pendingAction = null;
      await submitAction(action);
    });
    window.addEventListener("hashchange", () => {
      const previousScene = app.scene;
      const previousStep = app.pipelineStep;
      readHash();
      setView(app.view);
      if (app.scene !== previousScene) loadSession();
      if (app.view === "pipeline" && app.pipelineStep !== previousStep) renderPipeline();
    });
  }

  async function init() {
    readHash();
    bindEvents();
    setView(app.view);
    renderPipeline();
    await Promise.all([loadRoster(), loadSession()]);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
