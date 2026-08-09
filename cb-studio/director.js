(function () {
  "use strict";

  const app = {
    episode: "Ep1",
    scene: "1",
    shotId: null,
    activeBeatId: null,
    view: "director",
    pipelineStep: "upload",
    session: null,
    roster: null,
    directorBoard: null,
    references: null,
    referenceStage: "keyframe",
    inlineReferences: null,
    inlineReferencesKey: null,
    inlineReferencesLoading: false,
    keyframeLibrary: null,
    keyframeLibraryKey: null,
    keyframeLibraryLoading: false,
    sceneAssetLibrary: null,
    sceneAssetLibraryLoading: false,
    scenePlateLibraryOpen: false,
    workbenchState: null,
    workbenchSaveTimer: null,
    selectedCandidate: null,
    pendingAction: null,
    pendingAdvance: null,
    localActivity: null,
    activityTimer: null,
    voiceStatus: null,
    voiceStatusKey: null,
    voiceLoading: false,
    roughCutStatus: null,
    roughCutStatusKey: null,
    roughCutLoading: false,
    agentBrief: null,
    agentBriefKey: null,
    agentLoading: false,
    pollTimer: null,
    toastTimer: null,
    buildTimer: null,
    explicitLocation: false,
    explicitBeat: false,
    keyframeZoom: 1,
  };

  const STUDIO_BUILD = document.querySelector('meta[name="studio-build"]')?.content || "unknown";
  const relayNoteTimers = new WeakMap();

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const esc = (value) => String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  async function api(path, options, timeoutMs = path === "/api/director-action" ? 60000 : 15000) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    let response;
    try {
      response = await fetch(path, {
      cache: "no-store",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
      });
    } catch (error) {
      if (error.name === "AbortError") {
        const timedOut = new Error(
          path === "/api/director-action"
            ? "The Studio is still checking this decision. Its live status will be reconciled before you can act again."
            : "The Studio took too long to respond. Retry this action."
        );
        timedOut.code = path === "/api/director-action" ? "DIRECTOR_ACTION_TIMEOUT" : "REQUEST_TIMEOUT";
        throw timedOut;
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
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

  const sceneOneContract = {
    title: "Scene 1 — Fuzzby’s Pollination Lesson",
    promise: "Fuzzby’s joyful performance of expertise becomes increasingly visible failure, while Zenny’s restrained amusement shows that she sees and loves exactly who he is.",
    gates: ["Script", "Direction", "Keyframes", "Generate", "Review"],
    beats: [
      {
        id: "chase",
        n: 1,
        title: "Chase",
        range: "00.0–04.2s",
        priority: "required",
        reviewStatus: "delivered",
        shot: "SH1A",
        keyframe: "Flower-corridor chase starting composition",
        cta: "Generate Chase Keyframe",
        intent: "Fuzzby pursues pollen through the corridor.",
        scriptTruth: "Fuzzby enters as joyful chaos, trying to look expert while barely controlling the route.",
        visibleProof: "The audience sees a clear bee-height chase lane and two escalating near-misses.",
        startState: "Open flower corridor ahead; Fuzzby already overcommitted; Zenny clean and outside his path.",
        actionPath: "Drone-like pursuit → two near-misses → flower contact setup.",
        endState: "Fuzzby is still moving forward with room for the first crash.",
        camera: "Bee-height chase camera, slightly late, no confusing cuts.",
        checklist: [
          "Clear bee-height chase lane",
          "Two near-misses have room to stage",
          "Zenny has safe parallel route",
          "Camera axis is readable",
        ],
        failConditions: ["No static hovering", "No early crash", "No lost corridor route"],
        promptSegment: "Chase prompt segment: bee-height drone pursuit, open corridor, two readable near-misses, Zenny safely parallel.",
        reviewNote: "Chase route is readable and has room for escalation.",
      },
      {
        id: "triumph",
        n: 2,
        title: "False Triumph",
        range: "04.2–08.8s",
        priority: "required",
        reviewStatus: "delivered",
        shot: "SH1A",
        keyframe: "Fuzzby chest-out post-recoil hover",
        cta: "Generate False-Triumph Anchor",
        intent: "Fuzzby converts a crash into a proud finish.",
        scriptTruth: "The leaf recoil accidentally gives Fuzzby a gymnast-style recovery he pretends was planned.",
        visibleProof: "Flower scoop, springy leaf impact, recoil rotation, chest-out hover.",
        startState: "Fuzzby dives too hard into a flower.",
        actionPath: "Face contact → leaf bend → recoil → tucked rotation → proud hover.",
        endState: "Fuzzby is upright, proud and physically unsettled.",
        camera: "Hold the cause chain and settle on the false triumph.",
        checklist: [
          "Leaf recoil cause is visible",
          "Fuzzby has a clear chest-forward hover",
          "Minor instability remains readable",
          "Space exists for later flower action",
        ],
        failConditions: ["No random impact", "No painful collision", "No missing leaf recoil"],
        promptSegment: "False Triumph prompt segment: flower scoop, springy leaf recoil, tucked rotation and proud hover with residual wobble.",
        reviewNote: "False triumph reads as accidental success rather than real competence.",
      },
      {
        id: "moustache",
        n: 3,
        title: "Pollen Moustache",
        range: "08.8–16.2s",
        priority: "blocking",
        reviewStatus: "weak",
        shot: "SH1B",
        keyframe: "Moustache Setup",
        secondaryKeyframe: "Moustache Reveal",
        cta: "Generate Moustache Setup Keyframe",
        ctaAfterSetup: "Generate Moustache Reveal Keyframe",
        intent: "Escalate Fuzzby’s false expertise into a readable visual joke.",
        scriptTruth: "Fuzzby gets two pollen curls on his upper lip and presents them as authority.",
        visibleProof: "The pollen moustache must read before Zenny reacts.",
        startState: "Fuzzby centre-left; separate target flower centre-right; Zenny frame-left and outside his travel route.",
        actionPath: "Forward arc → face contacts target flower → pollen transfers → same-path return → presentation hold → Zenny reacts.",
        endState: "Two upper-lip pollen curls are visible, target flower remains visible, Fuzzby holds proudly.",
        camera: "Medium-wide, warm corridor, target flower and return position both readable.",
        timing: "Reveal hold around 0.8s before Zenny response.",
        checklist: [
          "Separate target flower visible",
          "Fuzzby’s forward route to flower is clear",
          "Zenny remains outside Fuzzby’s route",
          "Camera keeps flower, Fuzzby and Zenny readable",
          "No moustache exists in setup frame",
        ],
        revealChecklist: [
          "Two clear upper-lip pollen curls",
          "Target flower remains visible in background",
          "Fuzzby is in planned reveal position",
          "Fuzzby holds proudly before Zenny reacts",
          "Zenny’s eye-line lands on moustache first",
        ],
        failConditions: ["Fuzzby backs into Zenny", "Full-face pollen mask", "Target flower missing", "Zenny reacts too early"],
        recommendedFix: "Generate the Moustache Setup keyframe, then the Moustache Reveal keyframe, and use them as anchors for a dedicated 7.4-second Seedance shot.",
        promptSegment: "Moustache Setup prompt segment: Fuzzby centre-left, separate target flower centre-right, Zenny outside route, no moustache yet. Reveal segment: same flower remains visible, two upper-lip pollen curls, proud hold before Zenny reacts.",
        reviewNote: "Target flower and upper-lip moustache are unclear; route drifted toward Zenny instead of returning to the reveal position.",
      },
      {
        id: "zenny",
        n: 4,
        title: "Zenny Reaction",
        range: "14.0–16.2s",
        priority: "required",
        reviewStatus: "not-started",
        shot: "SH1B",
        keyframe: "Restrained, affectionate deadpan",
        cta: "Generate Zenny Reaction Keyframe",
        intent: "Zenny’s deadpan lands after the evidence.",
        scriptTruth: "Zenny judges the accident with restraint and affection.",
        visibleProof: "Her eyes move from moustache to Fuzzby before the response lands.",
        startState: "Moustache visible; Fuzzby presenting; Zenny close but outside route.",
        actionPath: "Evidence read → eye move → almost-smile → deadpan response.",
        endState: "Zenny’s affection is visible without broad mugging.",
        camera: "Relationship composition; no cut before the joke reads.",
        checklist: [
          "Moustache has already been established",
          "Zenny remains almost still",
          "Eye movement is directed to moustache, then Fuzzby",
          "One mouth corner only just lifts",
          "Reaction has no broad expression or early action",
        ],
        failConditions: ["Reaction before reveal", "Broad cartoon laugh", "Zenny blocking target flower"],
        promptSegment: "Zenny Reaction prompt segment: moustache already established, Zenny almost still, eyes to moustache then Fuzzby, tiny mouth-corner lift only.",
        reviewNote: "Reaction must wait until the moustache is visually established.",
      },
      {
        id: "payoff",
        n: 5,
        title: "Final Warmth",
        range: "16.2–29.0s",
        priority: "polish",
        reviewStatus: "not-started",
        shot: "SH1C",
        keyframe: "Shared final pose",
        cta: "Generate Final Payoff Keyframe",
        intent: "Fuzzby worsens the mess and Zenny loves him anyway.",
        scriptTruth: "A second failure becomes a warm character button.",
        visibleProof: "Fuzzby pops out more pollen-covered; Zenny eye-roll softens into love.",
        startState: "Fuzzby still marked with pollen; Zenny clear of the route.",
        actionPath: "Wipe-smear → overcommit → flower contacts → pop-up pose → softened eye-roll.",
        endState: "Golden dust hangs between Fuzzby and Zenny’s smiling eye-roll.",
        camera: "Follow causal tumble, then hold the final relationship frame.",
        checklist: [
          "Fuzzby is visibly more pollen-covered",
          "Final pose keeps both characters readable",
          "Zenny’s eye-roll softens into affection",
          "Golden dust hangs between them",
          "The shot ends on a usable handoff frame",
        ],
        failConditions: ["Random cuts", "No worsening", "No loving soften"],
        promptSegment: "Final Warmth prompt segment: Fuzzby worsens the pollen mess, pops into final readable pose, Zenny eye-roll softens into love, held handoff frame.",
        reviewNote: "Final warmth depends on a held two-character payoff, not more random chaos.",
      },
    ],
  };

  function readHash() {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    app.view = ["pipeline", "episodes", "director", "review"].includes(params.get("view"))
      ? params.get("view") : "director";
    app.scene = params.get("scene") || "1";
    app.shotId = params.get("shot") || null;
    app.explicitLocation = params.has("scene") || params.has("shot");
    app.activeBeatId = params.get("beat") || null;
    app.explicitBeat = params.has("beat");
    const requestedStep = { keyframes: "storyboard", animate: "footage", stitch: "rough-cut", post: "rough-cut" }[params.get("step")] || params.get("step");
    app.pipelineStep = pipelineSteps.some((step) => step.id === requestedStep)
      ? requestedStep : "storyboard";
  }

  function writeHash() {
    const params = new URLSearchParams({ view: app.view, scene: app.scene });
    if (app.shotId) params.set("shot", app.shotId);
    if (app.activeBeatId) params.set("beat", app.activeBeatId);
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

  function rosterScenes() {
    return app.roster?.scenes || [];
  }

  function currentRosterScene() {
    return rosterScenes().find((scene) => String(scene.sceneNumber) === String(app.scene)) || null;
  }

  function sceneHeading(scene) {
    if (!scene) return `Scene ${app.scene}`;
    return `${scene.location || `Scene ${scene.sceneNumber}`}${scene.time ? ` - ${scene.time}` : ""}`;
  }

  function renderSceneTiles() {
    const scenes = rosterScenes();
    return scenes.map((scene) => {
      const number = String(scene.sceneNumber);
      const current = number === String(app.scene);
      return `<button type="button" class="scene-tile ${current ? "current" : ""}" data-pipeline-scene="${esc(number)}">
        <span>${esc(number)}</span><strong>${esc(sceneHeading(scene))}</strong><em>${Number(scene.beatCount || 0)} beats</em>
      </button>`;
    }).join("") || '<div class="reference-unavailable">No approved scenes yet.</div>';
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
      resetShotScopedState();
      writeHash();
      loadSession();
    }));
  }

  function renderDirectorSceneStrip(session) {
    const host = $("#director-scene-strip");
    if (!host) return;
    const scenes = rosterScenes();
    host.innerHTML = `<button type="button" class="next-decision" data-next-decision>Back to my next decision</button>` + scenes.map((scene) => {
      const number = String(scene.sceneNumber);
      const current = number === String(session.scene || app.scene);
      const board = (app.directorBoard?.scenes || []).find((item) => String(item.scene) === number) || {};
      return `<button type="button" data-director-scene="${esc(number)}" class="${current ? "active" : ""}" aria-current="${current ? "true" : "false"}">
        <span>Scene ${esc(number)}</span>
        <strong>${esc(scene.location || `Scene ${number}`)}</strong><em>${esc(board.statusLabel || "Not started")}</em>
      </button>`;
    }).join("") || '<span class="reference-unavailable">No approved scenes yet.</span>';
    host.querySelectorAll("[data-director-scene]").forEach((button) => button.addEventListener("click", () => {
      const scene = button.dataset.directorScene;
      if (scene === String(app.scene)) return;
      app.scene = scene;
      app.shotId = null;
      resetShotScopedState();
      writeHash();
      loadSession();
    }));
    host.querySelector("[data-next-decision]")?.addEventListener("click", openNextDecision);
  }

  function openNextDecision() {
    const next = app.directorBoard?.nextDecision;
    if (!next) {
      toast("There are no sign-offs waiting. Open Scenes to start another scene.");
      setView("episodes");
      return;
    }
    app.scene = String(next.scene);
    app.shotId = next.shotId || null;
    resetShotScopedState();
    writeHash();
    setView("director");
    loadSession();
  }

  function resetShotScopedState() {
    app.activeBeatId = null;
    app.explicitBeat = false;
    app.voiceStatus = null;
    app.voiceStatusKey = null;
    app.voiceLoading = false;
    app.agentBrief = null;
    app.agentBriefKey = null;
    app.agentLoading = false;
    app.references = null;
    app.inlineReferences = null;
    app.inlineReferencesKey = null;
    app.inlineReferencesLoading = false;
    app.workbenchState = null;
    app.selectedCandidate = null;
  }

  function agentKey(session) {
    if (!session) return null;
    return `${session.episode}:${session.scene}:${session.selectedShotId || "-"}`;
  }

  function renderStudioAgent() {
    const host = $("#studio-agent-panel");
    if (!host) return;
    const session = app.session;
    const expectedKey = agentKey(session);
    if (!session) {
      host.innerHTML = `<div><span class="stage-label">Studio Agent</span><strong>Loading production state...</strong><p>No scene is selected yet.</p></div>`;
      return;
    }
    if (app.agentLoading && app.agentBriefKey !== expectedKey) {
      host.innerHTML = `<div><span class="stage-label">Studio Agent</span><strong>Checking the current production state...</strong><p>Read-only guidance. No data is changed and no provider is called.</p></div>`;
      return;
    }
    const brief = app.agentBrief;
    if (!brief || app.agentBriefKey !== expectedKey) {
      host.innerHTML = `<div><span class="stage-label">Studio Agent</span><strong>Ready to advise this step.</strong><p>Guidance will appear when the scene state finishes loading.</p></div>`;
      return;
    }
    if (brief.error) {
      host.innerHTML = `<div><span class="stage-label">Studio Agent</span><strong>Agent unavailable</strong><p>${esc(brief.error)}</p></div>`;
      return;
    }
    const next = brief.nextAction || {};
    const facts = brief.facts || {};
    const proven = (facts.proven || []).length;
    const built = (facts.built || []).length;
    const currentAction = [session.primaryAction, ...(session.decisionActions || [])]
      .filter(Boolean)
      .map((action) => action.id === "approve-spend" ? "Render 480p" : action.id.startsWith("iterate-") ? "Refire" : action.id.startsWith("accept-") ? "Approve" : action.label)
      .join(" / ");
    host.innerHTML = `<div>
      <span class="stage-label">Studio Agent · Read-only</span>
      <strong>${esc(session.headline || brief.headline || "Current production guidance")}</strong>
      <p>${esc(session.summary || next.label || "Review the current production state.")}</p>
    </div>
    <div class="agent-meta">
      <span>${esc(phaseLabel(session.phase))}</span>
      <span>${esc(currentAction || next.type || "guidance")}</span>
      <span>${built} built</span>
      <span>${proven} proven</span>
    </div>`;
  }

  async function loadStudioAgent(force = false) {
    const session = app.session;
    const key = agentKey(session);
    if (!key || (!force && (app.agentLoading || app.agentBriefKey === key))) return;
    app.agentLoading = true;
    app.agentBriefKey = key;
    renderStudioAgent();
    const shot = session.selectedShotId ? `&shotId=${encodeURIComponent(session.selectedShotId)}` : "";
    try {
      app.agentBrief = await api(`/api/studio-agent?mode=HELP&episode=${encodeURIComponent(session.episode)}&scene=${encodeURIComponent(session.scene)}${shot}`);
    } catch (error) {
      app.agentBrief = { error: error.message };
    } finally {
      app.agentLoading = false;
      renderStudioAgent();
    }
  }

  function renderAdvisories(session) {
    const host = $("#director-advisories");
    if (!host) return "";
    const items = session.advisories || [];
    host.hidden = !items.length;
    host.innerHTML = items.map((item) => `<article class="director-advisory ${esc(item.severity || "info")}">
      <strong>${esc(item.title || "Production note")}</strong>
      <p>${esc(item.message || "")}</p>
      ${item.nextAction ? `<em>${esc(item.nextAction)}</em>` : ""}
      ${(item.signals || []).length ? `<span>${(item.signals || []).map(esc).join(" · ")}</span>` : ""}
    </article>`).join("");
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

  function formatRenderElapsed(started) {
    const elapsed = Math.max(0, Math.floor(Date.now() / 1000 - Number(started || Date.now() / 1000)));
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function renderProgress(session) {
    const job = session.runningJob || {};
    const activityLabel = job.activityLabel || (session.phase === "animation" ? "Render in progress" : "Build in progress");
    const provider = job.providerModelId || session.providerModel || "Production provider";
    const duration = Number(job.durationSec || session.shot?.durationSec || 0);
    const candidates = Number(job.candidateCount || 0);
    const cost = Number(job.maxBatchCostUsd || 0);
    const providerLabel = session.phase === "animation" ? provider : "Opening-frame build";
    const trackLabel = session.phase === "animation" ? "Provider render is active" : "Studio build is active";
    const fallbackMessage = session.phase === "animation"
      ? "The request has been submitted and the provider is processing it."
      : "The Studio is building this step. No animation render has been submitted.";
    const details = [
      session.phase === "animation" && duration ? `${duration}s clip` : "",
      candidates ? `${candidates} candidate${candidates === 1 ? "" : "s"}` : "",
      cost ? `up to $${cost.toFixed(2)}` : "",
    ].filter(Boolean);
    return `<div class="render-progress" role="status" aria-live="polite">
      <div class="render-progress-head">
        <span class="loading-mark" aria-hidden="true"></span>
        <div><span class="render-kicker">${esc(activityLabel)}</span><strong>${esc(job.step || "Building the next result...")}</strong></div>
        <time aria-label="Elapsed activity time">${formatRenderElapsed(job.started)}</time>
      </div>
      <div class="render-progress-track" aria-label="${esc(trackLabel)}"><span></span></div>
      <div class="render-progress-meta"><span>${esc(providerLabel)}</span>${details.map((item) => `<span>${esc(item)}</span>`).join("")}</div>
      <p>${esc(job.latestMessage || fallbackMessage)}</p>
      <small>${esc(session.phase === "animation" ? "Live activity. The provider does not supply a reliable completion percentage or ETA." : "Live activity. This step will update automatically when the result is ready.")}</small>
    </div>`;
  }

  function actionActivityCopy(action, session, preparingRetry) {
    if (action.id === "accept-keyframe") {
      return {
        label: "Accepting keyframe",
        step: "Locking this frame as the shot truth...",
        message: "Your sign-off is being recorded. No provider generation or spend is occurring.",
        provider: "Studio approval",
        showDuration: false,
      };
    }
    if (action.id === "iterate-keyframe") {
      return {
        label: "Keyframe refire in progress",
        step: "Applying your note and building a corrected opening frame...",
        message: "Your retake note is recorded. Seedream is generating the replacement for your review.",
        provider: "Seedream 5 Pro",
        showDuration: false,
      };
    }
    if (action.id === "iterate-voice") {
      return {
        label: "Voice refire in progress",
        step: "Applying your note and preparing the corrected performance...",
        message: "Your retake note is recorded. The replacement voice will return here for your review.",
        provider: "ElevenLabs",
        showDuration: false,
      };
    }
    if (preparingRetry) {
      return {
        label: "Refire preparation",
        step: "Archiving the rejected take and preparing the corrected request...",
        message: "No provider spend is occurring yet. The corrected request will be shown for approval before rendering.",
        provider: "Studio direction",
        showDuration: false,
      };
    }
    if (action.id === "build-keyframe") {
      return {
        label: "Keyframe build in progress",
        step: "Building the opening frame in Seedream 5 Pro...",
        message: "This is the still stage. No Seedance animation render has been submitted.",
        provider: "Seedream 5 Pro",
        showDuration: false,
      };
    }
    if (action.id === "build-voice") {
      return {
        label: "Voice generation in progress",
        step: "Creating the approved dialogue performance...",
        message: "This is the ElevenLabs dialogue stage. No animation render has been submitted.",
        provider: "ElevenLabs",
        showDuration: false,
      };
    }
    if (action.id === "prepare-render") {
      return {
        label: "Preparing animation request",
        step: "Preparing the Seedance request for approval...",
        message: "No provider spend is occurring yet. You will see the sealed request before render approval.",
        provider: "Studio direction",
        showDuration: false,
      };
    }
    if (action.id === "approve-spend") {
      return {
        label: "Render in progress",
        step: "Submitting the approved Seedance request...",
        message: "The sealed request is being submitted to the provider.",
        provider: session.providerModel,
        showDuration: true,
      };
    }
    return {
      label: "Build in progress",
      step: `${action.label || "Working"}...`,
      message: "The Studio is working on the selected shot.",
      provider: "Studio generation",
      showDuration: false,
    };
  }

  function renderGenerateStatus(session) {
    const serverJob = session.runningJob;
    const activity = app.localActivity || (serverJob ? {
      id: serverJob.jobId || `server-job-${session.selectedShotId}`,
      actionId: "server-job",
      shotId: session.selectedShotId,
      started: serverJob.started,
      state: "running",
      label: serverJob.activityLabel || "Studio work in progress",
      step: serverJob.step || "Building the next result...",
      message: serverJob.latestMessage || "The Studio is still working. This view will update automatically.",
      providerModelId: serverJob.providerModelId,
      durationSec: serverJob.durationSec,
      candidateCount: serverJob.candidateCount,
      showDuration: session.phase === "animation",
    } : null);
    if (!activity || activity.shotId !== session.selectedShotId) {
      const spend = session.spendDisclosure;
      if (!spend) return "";
      return `<div class="generate-status sealed" role="status" aria-live="polite">
        <div><span>Render ready</span><strong>Sealed request awaiting your approval</strong></div>
        <p>No video is rendering yet. Review the maximum cost, then approve the render.</p>
        <small>${esc(spend.providerModelId || session.providerModel || "Seedance")} · ${esc(spend.resolution || "480p")} · ${esc(Number(spend.shotDurationSec || 0))}s · max $${Number(spend.maxBatchCostUsd || 0).toFixed(2)}</small>
      </div>`;
    }
    const held = activity.state === "held";
    const details = [
      activity.providerModelId,
      activity.showDuration && activity.durationSec ? `${Number(activity.durationSec)}s clip` : "",
      activity.showDuration && activity.resolution ? activity.resolution : "",
      activity.candidateCount ? `${Number(activity.candidateCount)} candidate${Number(activity.candidateCount) === 1 ? "" : "s"}` : "",
    ].filter(Boolean);
    return `<div class="generate-status ${held ? "held" : ""}" role="status" aria-live="polite">
      <div>
        <span>${esc(activity.label)}</span>
        <strong>${esc(activity.step)}</strong>
      </div>
      <time data-activity-elapsed="${esc(activity.id)}">${formatRenderElapsed(activity.started)}</time>
      ${held ? `<p>${esc(activity.message || "The result was held back. Review the note, then build again.")}</p>` : ""}
      ${!held && activity.message ? `<p>${esc(activity.message)}</p>` : ""}
      ${details.length ? `<small>${details.map(esc).join(" · ")}</small>` : ""}
    </div>`;
  }

  function refreshActivityElapsed() {
    if (!app.localActivity) return;
    $$(`[data-activity-elapsed="${CSS.escape(app.localActivity.id)}"]`)
      .forEach((node) => { node.textContent = formatRenderElapsed(app.localActivity.started); });
  }

  function setLocalActivity(activity) {
    app.localActivity = activity;
    clearInterval(app.activityTimer);
    if (activity) app.activityTimer = setInterval(refreshActivityElapsed, 1000);
  }

  function holdLocalActivity(action, session, message, label = "Action refused") {
    setLocalActivity({
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      actionId: action?.id || "director-action",
      shotId: session?.selectedShotId || app.session?.selectedShotId,
      started: Date.now() / 1000,
      state: "held",
      label,
      step: message,
      message,
    });
  }

  function clearLocalActivityForSession(session) {
    if (!app.localActivity || app.localActivity.shotId !== session.selectedShotId) return;
    if (app.localActivity.state === "held") return;
    if (session.status === "rendering") return;
    if (!session.runningJob) {
      if (
        app.localActivity.actionId === "build-keyframe" &&
        session.phase === "keyframe" &&
        session.status === "ready_to_fire" &&
        !(session.shots || []).find((shot) => shot.selected)?.keyframeUrl
      ) {
        setLocalActivity({
          ...app.localActivity,
          state: "held",
          label: "Keyframe held back",
          step: "Seedream returned a frame, but QC did not pass it.",
          message: "No animation render was submitted. Press Build opening frame again, or use Refire when a review image is visible.",
        });
        return;
      }
      setLocalActivity(null);
      return;
    }
    const activeIds = [session.primaryAction, ...(session.decisionActions || [])]
      .filter(Boolean)
      .map((action) => action.id);
    if (activeIds.includes(app.localActivity.actionId)) return;
    setLocalActivity(null);
  }

  function renderArtifact(session) {
    const stage = $("#media-stage");
    const artifact = session.artifact || {};
    app.selectedCandidate = null;
    if (session.status === "rendering") {
      stage.innerHTML = renderProgress(session);
      return;
    }
    if (artifact.type === "image" && artifact.url) {
      stage.innerHTML = `<span class="stage-badge">${esc(artifact.label || "Current image")}</span><img src="${esc(artifact.url)}?v=${Date.now()}" alt="${esc(artifact.label || "Current production image")}">`;
      return;
    }
    if (artifact.type === "audio" && artifact.url) {
      const selectedShot = (session.shots || []).find((shot) => shot.selected) || {};
      const keyframeUrl = selectedShot.keyframeUrl || "";
      stage.innerHTML = `<div class="voice-review-stage">
        ${keyframeUrl ? `<figure>
          <span>Approved opening keyframe</span>
          <img src="${esc(keyframeUrl)}?v=${Date.now()}" alt="Approved opening keyframe for this shot">
        </figure>` : `<figure class="missing">
          <span>No keyframe visible</span>
          <strong>The voice take exists, but no approved keyframe URL is available for this shot.</strong>
        </figure>`}
        <div class="voice-review-player">
          <span>${esc(artifact.label || "Voice performance")}</span>
          <strong>Approve or refire the dialogue performance only.</strong>
          <audio controls preload="metadata" src="${esc(artifact.url)}?v=${Date.now()}"></audio>
        </div>
      </div>`;
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
    if (session.spendDisclosure && (session.decisionActions || []).some((action) => action.id === "approve-spend")) {
      const spend = session.spendDisclosure;
      const renderAction = (session.decisionActions || []).find((action) => action.id === "approve-spend");
      const cancelAction = (session.decisionActions || []).find((action) => action.id === "cancel-spend");
      stage.innerHTML = `<div class="render-ready-panel" role="status" aria-live="polite">
        <span class="render-kicker">Retry prepared</span>
        <h3>Ready to render ${esc(spend.resolution || "480p")}</h3>
        <p>The corrected request is sealed and waiting for approval. No new Seedance video exists until this render is submitted.</p>
        <div class="render-ready-meta">
          <span>${esc(spend.providerModelId || session.providerModel || "Seedance")}</span>
          <span>${esc(Number(spend.shotDurationSec || session.shot?.durationSec || 0))}s</span>
          <span>${esc(spend.candidateCount || 1)} candidate</span>
          <span>max $${Number(spend.maxBatchCostUsd || 0).toFixed(2)}</span>
        </div>
        <div class="render-ready-actions">
          ${renderAction ? `<button type="button" class="primary" data-stage-action="${esc(renderAction.id)}">Render ${esc(spend.resolution || "480p")}</button>` : ""}
          ${cancelAction ? `<button type="button" class="secondary" data-stage-action="${esc(cancelAction.id)}">Not yet</button>` : ""}
        </div>
      </div>`;
      stage.querySelectorAll("[data-stage-action]").forEach((button) => button.addEventListener("click", () => {
        const actions = [session.primaryAction, ...(session.decisionActions || [])].filter(Boolean);
        const action = actions.find((item) => item.id === button.dataset.stageAction);
        if (action) handleAction(action);
      }));
      return;
    }
    if (session.phase === "story") {
      stage.innerHTML = emptyStage("This scene has not been directed into production shots yet.", false);
      return;
    }
    stage.innerHTML = emptyStage(session.status === "blocked" ? "No result can be built from the current route yet." : "No rendered result yet.", false);
  }

  function currentReferenceStage(session) {
    return ["animation", "review", "final"].includes(session.phase) ? "animation" : "keyframe";
  }

  function requestPromptText(session) {
    const request = session.inspector?.providerRequest;
    if (!request) return "No provider request has been prepared for this phase yet.";
    return request.prompt || (request.lines || []).map((line) => `${line.speaker}: ${line.performedText}`).join("\n") || "No provider text is required for this step.";
  }

  async function copyVisiblePrompt(button) {
    const panel = button.closest("[data-prompt-copy-panel]");
    const prompt = panel?.querySelector("pre")?.textContent || "";
    if (!prompt.trim()) {
      toast("There is no prompt to copy yet.", true);
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(prompt);
      } else {
        const fallback = document.createElement("textarea");
        fallback.value = prompt;
        fallback.setAttribute("readonly", "");
        fallback.style.position = "fixed";
        fallback.style.opacity = "0";
        document.body.appendChild(fallback);
        fallback.select();
        if (!document.execCommand("copy")) throw new Error("Clipboard unavailable");
        fallback.remove();
      }
      const status = panel.querySelector("[data-copy-prompt-status]");
      if (status) status.textContent = "Copied";
      button.classList.add("copied");
      button.title = "Prompt copied";
      window.setTimeout(() => {
        if (status) status.textContent = "";
        button.classList.remove("copied");
        button.title = "Copy prompt";
      }, 1800);
    } catch (_) {
      toast("The prompt could not be copied. Select the prompt text and copy it manually.", true);
    }
  }

  function bindPromptCopyButtons(root) {
    root.querySelectorAll("[data-copy-prompt]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        copyVisiblePrompt(button);
      });
    });
  }

  function renderShotInputs(session) {
    const host = $("#shot-inputs");
    if (!host) return;
    const shot = (session.shots || []).find((item) => item.selected) || session.shot || {};
    if (!session.selectedShotId) {
      host.innerHTML = '<div class="shot-inputs-empty">Select or build a shot to see its scene plate, character references and prompt.</div>';
      return;
    }
    const stage = currentReferenceStage(session);
    const referencesCurrent = app.inlineReferencesKey === `${session.episode}:${session.scene}:${session.selectedShotId}`;
    const stageData = referencesCurrent ? (app.inlineReferences?.[stage] || {}) : {};
    const refs = referencesCurrent
      ? (stageData.references || [])
      : [];
    const referenceMessage = app.inlineReferencesLoading
      ? "Loading locked references..."
      : stageData.error
        ? `Reference load failed: ${stageData.error}`
        : "";
    const plateRefs = refs.filter((item) => /scene|plate|location|look|corridor|environment/i.test(`${item.role || ""} ${item.label || ""} ${item.slot || ""}`));
    const characterRefs = refs.filter((item) => item.identity?.intactTurnaround || /character|turnaround|zenny|fuzzby|aida|keen|lunar|squeaky/i.test(`${item.role || ""} ${item.label || ""} ${item.slot || ""}`));
    const otherRefs = refs.filter((item) => !plateRefs.includes(item) && !characterRefs.includes(item));
    const renderRef = (item) => {
      const label = item.role || item.label || "Shot reference";
      const isAudio = Boolean(item.url) && (
        item.kind === "audio" || /\.(?:wav|mp3|m4a|aac|ogg)(?:\?|$)/i.test(item.url) ||
        /audio|voice|dialogue|performance track/i.test(label));
      return `<article class="shot-input-ref ${isAudio ? "audio-reference" : ""}">
      ${isAudio ? audioWaveformMarkup(label) : item.url ? `<img src="${esc(item.url)}" alt="${esc(label)}">` : '<div class="shot-input-ref-missing">Missing</div>'}
      <strong>${esc(item.role || item.label || item.slot || "Reference")}</strong>
      <span>${esc(item.identity?.intactTurnaround ? "Complete uncropped turnaround · identity authority" : item.message || item.status || "Locked reference")}</span>
    </article>`;
    };
    const prompt = requestPromptText(session);
    const phaseName = session.phase === "voice"
      ? "Voice performance"
      : stage === "animation" ? "Animation" : "Keyframe";
    const phaseCopy = session.phase === "voice"
      ? "Review the approved keyframe context, the current ElevenLabs acting prompt and the generated take. No animation render is submitted at this stage."
      : stage === "animation"
        ? "Approve the keyframe first. Animation uses that approved frame, the same locked references and this exact Seedance request."
        : "Create the still frame first. This image becomes the visual truth for the shot before animation is allowed.";
    const phaseAction = session.status === "rendering"
      ? "Working"
      : session.primaryAction
        ? directorActionLabel(session.primaryAction)
        : directorActionLabel((session.decisionActions || [])[0]) || "Review";
    host.innerHTML = `<div class="shot-inputs-head">
      <div>
        <span class="stage-label">${esc(phaseName)} inputs</span>
        <h2>${esc(shot.shotId || session.selectedShotId)} · ${esc(shot.title || session.sceneName || "Current shot")}</h2>
        <p>${esc(phaseCopy)}</p>
      </div>
      <div class="shot-inputs-phase">
        <span>${esc(phaseLabel(session.phase))}</span>
        <strong>${esc(phaseAction)}</strong>
      </div>
    </div>
    <div class="shot-input-grid">
      <section>
        <div class="shot-input-section-head"><span>Scene Plate</span><strong>${referenceMessage ? "..." : plateRefs.length || 0}</strong></div>
        <div class="shot-input-ref-grid">${plateRefs.map(renderRef).join("") || `<div class="shot-inputs-empty">${esc(referenceMessage || "No scene plate reference loaded yet.")}</div>`}</div>
      </section>
      <section>
        <div class="shot-input-section-head"><span>Character Turnarounds</span><strong>${referenceMessage ? "..." : characterRefs.length || 0}</strong></div>
        <div class="shot-input-ref-grid">${characterRefs.map(renderRef).join("") || `<div class="shot-inputs-empty">${esc(referenceMessage || "No character turnaround loaded yet.")}</div>`}</div>
      </section>
    </div>
    ${otherRefs.length ? `<section><div class="shot-input-section-head"><span>Other Locked References</span><strong>${otherRefs.length}</strong></div><div class="shot-input-ref-grid compact">${otherRefs.map(renderRef).join("")}</div></section>` : ""}
    <section class="shot-prompt-panel" data-prompt-copy-panel>
      <div class="shot-input-section-head"><span>Exact Prompt</span><div class="prompt-copy-actions"><strong>${session.inspector?.providerRequest ? "Prepared" : "Pending"}</strong><span class="prompt-copy-status" data-copy-prompt-status aria-live="polite"></span><button type="button" class="prompt-copy-button" data-copy-prompt aria-label="Copy prompt" title="Copy prompt"><span aria-hidden="true"></span></button></div></div>
      <pre>${esc(prompt)}</pre>
    </section>
    <section class="shot-handoff-rule">
      <strong>Continuity rule</strong>
      <p>If animation is approved, the final accepted frame becomes the handoff truth for the next shot in this scene. The next shot still uses its own scene plate, character turnarounds and prompt.</p>
    </section>`;
    bindPromptCopyButtons(host);
  }

  async function loadInlineShotContext(session) {
    const key = `${session.episode}:${session.scene}:${session.selectedShotId || ""}`;
    if (!session.selectedShotId || app.inlineReferencesKey === key || app.inlineReferencesLoading) {
      renderShotInputs(session);
      return;
    }
    app.inlineReferencesLoading = true;
    app.inlineReferencesKey = key;
    app.inlineReferences = null;
    renderShotInputs(session);
    try {
      app.inlineReferences = await api(`/api/shot-references?episode=${encodeURIComponent(session.episode)}&scene=${encodeURIComponent(session.scene)}&shotId=${encodeURIComponent(session.selectedShotId)}`, undefined, 60000);
    } catch (error) {
      app.inlineReferences = { keyframe: { references: [], error: error.message }, animation: { references: [], error: error.message } };
    } finally {
      app.inlineReferencesLoading = false;
      if (app.session?.selectedShotId === session.selectedShotId) {
        renderShotInputs(app.session);
      }
    }
  }

  function statusLabel(value) {
    return {
      delivered: "Delivered",
      approved: "Approved",
      review: "Review",
      working: "Working",
      weak: "Weak",
      missing: "Missing",
      contradicted: "Contradicted",
      "not-started": "Not started",
    }[value] || value || "Pending";
  }

  function workbenchStatusLabel(session, beat) {
    if (session.status === "rendering") return "WORKING";
    if (session.phase === "voice") {
      return session.status === "ready_to_review" ? "VOICE REVIEW" : "VOICE REQUIRED";
    }
    if (session.phase === "animation") {
      return session.status === "ready_to_review" ? "ANIMATION REVIEW" :
        session.status === "ready_to_fire" ? "ANIMATION READY" : "ANIMATION";
    }
    if (session.phase === "review") return "SHOT REVIEW";
    if (session.phase === "final") return session.status === "complete" ? "COMPLETE" : "MASTER REVIEW";
    return beat.priority === "blocking" && beat.reviewStatus === "weak"
      ? "KEYFRAME REQUIRED"
      : statusLabel(beat.reviewStatus).toUpperCase();
  }

  function workbenchPanelStatusLabel(session, beat) {
    if (session.phase === "voice") return "Voice review";
    if (session.phase === "animation") return session.status === "ready_to_review" ? "Animation review" : "Generate";
    if (session.phase === "review") return "Shot review";
    if (session.phase === "final") return "Master";
    return statusLabel(beat.reviewStatus);
  }

  function currentBeat() {
    return workbenchBeats().find((beat) => beat.id === app.activeBeatId) || workbenchBeats()[2];
  }

  function persistedBeat(beat) {
    const saved = app.workbenchState?.beatState?.[beat.id];
    return saved && typeof saved === "object" ? { ...beat, ...saved } : beat;
  }

  function workbenchBeats() {
    return sceneOneContract.beats.map(persistedBeat);
  }

  function shotKeyForBeat(beat) {
    const shot = String(beat?.shot || "");
    return shot.startsWith("S1.") ? shot : `S1.${shot}`;
  }

  function displayBeatState(beat, session) {
    const selectedShot = session?.selectedShotId || "";
    if (shotKeyForBeat(beat) !== selectedShot) return beat;
    if (session.status === "rendering") {
      return { ...beat, reviewStatus: "working" };
    }
    if (session.phase === "keyframe" && session.status === "ready_to_review") {
      return { ...beat, reviewStatus: "review" };
    }
    if (session.phase === "keyframe" && session.status === "ready_to_fire") {
      return { ...beat, reviewStatus: "missing" };
    }
    if (["voice", "animation", "review", "final"].includes(session.phase)) {
      return { ...beat, reviewStatus: "approved" };
    }
    return beat;
  }

  async function loadProjectWorkbenchState() {
    try {
      app.workbenchState = await api(`/api/project-workbench-state?project=crystal-bears&episode=${encodeURIComponent(app.episode)}&scene=${encodeURIComponent(app.scene)}`);
      if (!app.explicitBeat && app.workbenchState?.activeBeatId) {
        app.activeBeatId = app.workbenchState.activeBeatId;
      }
    } catch (_) {
      app.workbenchState = null;
    }
  }

  function saveProjectWorkbenchState(partial) {
    clearTimeout(app.workbenchSaveTimer);
    app.workbenchSaveTimer = setTimeout(async () => {
      try {
        app.workbenchState = await api("/api/project-workbench-state", {
          method: "POST",
          body: JSON.stringify({
            project: "crystal-bears",
            episode: app.episode,
            scene: app.scene,
            activeBeatId: app.activeBeatId,
            ...(partial || {}),
          }),
        }).then((payload) => payload.state);
        $("#save-state").textContent = "Saved";
      } catch (error) {
        $("#save-state").textContent = "Save failed";
        toast(error.message, true);
      }
    }, 150);
  }

  function workbenchPrimaryAction(session, beat) {
    const actions = [session.primaryAction, ...(session.decisionActions || [])].filter(Boolean);
    const accept = actions.find((action) => action.id.startsWith("accept-"));
    const iterate = actions.find((action) => action.id.startsWith("iterate-"));
    const spend = actions.find((action) => action.id === "approve-spend");
    const hasVisibleKeyframe = session.phase !== "keyframe" ||
      (session.artifact?.type === "image" && Boolean(session.artifact?.url));
    if (beat.reviewStatus === "weak" && iterate) return { action: iterate, label: beat.cta || "Refine Keyframe" };
    if (spend) {
      const cost = Number(session.spendDisclosure?.maxBatchCostUsd || 0).toFixed(2);
      return { action: spend, label: `Approve $${cost} & render` };
    }
    if (accept && hasVisibleKeyframe) return { action: accept, label: directorActionLabel(accept) };
    if (session.primaryAction) {
      return {
        action: session.primaryAction,
        label: session.phase === "keyframe" ? (beat.cta || session.primaryAction.label) : session.primaryAction.label,
      };
    }
    return null;
  }

  function renderWorkbenchRefs(session) {
    const stageData = app.inlineReferences?.[currentReferenceStage(session)] || {};
    const refs = stageData.references || [];
    if (!refs.length) {
      const message = app.inlineReferencesLoading
        ? "References loading"
        : stageData.error
          ? "References failed"
          : "References unavailable";
      return `<div class="workbench-ref-chip locked ${stageData.error ? "error" : ""}" title="${esc(stageData.error || message)}"><span>REF</span><strong>${esc(message)}</strong><em>LOCKED</em></div>`;
    }
    return refs.slice(0, 6).map((item) => `<div class="workbench-ref-chip locked" title="${esc(item.message || item.status || "Locked reference")}">
      ${item.url ? `<img src="${esc(item.url)}" alt="${esc(item.role || item.label || "Reference")}">` : "<span>REF</span>"}
      <strong>${esc(item.role || item.label || item.slot || "Reference")}</strong>
      <em>${esc(item.identity?.intactTurnaround ? "TURNAROUND" : "APPROVED")}</em>
    </div>`).join("");
  }

  function hasVisibleKeyframeArtifact(session) {
    return session?.phase === "keyframe" &&
      session?.artifact?.type === "image" &&
      Boolean(session.artifact.url);
  }

  function keyframeSourceLocked(session) {
    return hasVisibleKeyframeArtifact(session) || session?.status === "rendering";
  }

  async function loadKeyframeLibrary(session) {
    if (!session?.selectedShotId || session.phase !== "keyframe") return;
    const key = `${session.episode}:${session.scene}:${session.selectedShotId}`;
    if (app.keyframeLibraryKey === key || app.keyframeLibraryLoading) return;
    app.keyframeLibraryLoading = true;
    app.keyframeLibraryKey = key;
    try {
      app.keyframeLibrary = await api(`/api/shot-keyframe-library?episode=${encodeURIComponent(session.episode)}&scene=${encodeURIComponent(session.scene)}&shotId=${encodeURIComponent(session.selectedShotId)}`);
    } catch (error) {
      app.keyframeLibrary = { error: error.message, items: [] };
    } finally {
      app.keyframeLibraryLoading = false;
    }
  }

  function assetPathToUrl(path) {
    if (!path) return "";
    const clean = String(path).replace(/^\/+/, "");
    if (clean.startsWith("cb-seed/assets/")) return `/${clean}`;
    if (clean.startsWith("engine/media/")) return `/${clean}`;
    if (clean.startsWith("projects/")) return `/${clean}`;
    return "";
  }

  function assetPathToAbsolute(path) {
    const clean = String(path || "").replace(/^\/+/, "");
    return `/Users/julianjenkins/Desktop/8Th Hour v2.2/canonical/${clean}`;
  }

  async function loadSceneAssetLibrary() {
    if (app.sceneAssetLibrary || app.sceneAssetLibraryLoading) return;
    app.sceneAssetLibraryLoading = true;
    try {
      const [loclib, houses] = await Promise.all([
        api("/api/loclib"),
        api("/api/houses"),
      ]);
      const items = [];
      const manifest = loclib.manifest || {};
      Object.keys(manifest).forEach((key) => {
        const item = manifest[key] || {};
        const rel = item.file ? `cb-seed/assets/locations/${item.file}` : "";
        if (assetPathToUrl(rel)) {
          items.push({
            type: "Location",
            title: item.name || item.locationId || key,
            subtitle: item.source || item.location || "Reusable scene plate",
            path: assetPathToAbsolute(rel),
            url: assetPathToUrl(rel),
          });
        }
      });
      (loclib.uploadedRefs || []).forEach((item) => {
        const rel = item.file || "";
        if (assetPathToUrl(rel)) {
          items.push({
            type: "Scene",
            title: item.name || rel.split("/").pop(),
            subtitle: "Uploaded scene reference",
            path: assetPathToAbsolute(rel),
            url: assetPathToUrl(rel),
          });
        }
      });
      (loclib.scenes || []).forEach((item) => {
        if (item.master) {
          const rel = String(item.master).replace(/^\/+/, "");
          if (assetPathToUrl(rel)) {
            items.push({
              type: "Scene master",
              title: item.name || item.location || `Scene ${item.scene}`,
              subtitle: `Scene ${item.scene} · ${item.time || "scene plate"}`,
              path: assetPathToAbsolute(rel),
              url: assetPathToUrl(rel),
            });
          }
        }
      });
      (houses.houses || []).forEach((house) => {
        [
          ["House interior", house.interior],
          ["House interior multicam", house.interiorMulticam],
          ["House exterior", house.exterior],
          ["House exterior multicam", house.exteriorMulticam],
        ].forEach(([type, rel]) => {
          if (assetPathToUrl(rel)) {
            items.push({
              type,
              title: `${house.character} ${type.replace("House ", "")}`,
              subtitle: type.includes("interior") ? house.interiorDesc : house.exteriorDesc,
              path: assetPathToAbsolute(rel),
              url: assetPathToUrl(rel),
            });
          }
        });
      });
      const seen = new Set();
      app.sceneAssetLibrary = items.filter((item) => {
        if (!item.path || seen.has(item.path)) return false;
        seen.add(item.path);
        return true;
      });
    } catch (error) {
      app.sceneAssetLibrary = { error: error.message, items: [] };
    } finally {
      app.sceneAssetLibraryLoading = false;
    }
  }

  function renderKeyframeSourcePanel(session) {
    if (session.phase !== "keyframe") return "";
    const locked = keyframeSourceLocked(session);
    const items = app.keyframeLibrary?.items || [];
    const libraryReady = app.keyframeLibraryKey === `${session.episode}:${session.scene}:${session.selectedShotId}`;
    const sourceMessage = locked
      ? "A keyframe candidate is already waiting. Review it, approve it, or refire it before replacing the source."
      : "Pick a previous keyframe from this shot's library, upload your own frame, or generate a new one.";
    const assetItems = Array.isArray(app.sceneAssetLibrary) ? app.sceneAssetLibrary : [];
    const assetError = app.sceneAssetLibrary && !Array.isArray(app.sceneAssetLibrary) ? app.sceneAssetLibrary.error : "";
    const sceneLook = session.sceneLook || {};
    const scenePlateUrl = sceneLook.plateUrl || sceneLook.approved?.url || sceneLook.candidate?.url || "";
    const scenePlateLabel = sceneLook.activeSource === "working"
      ? "Pending scene plate"
      : sceneLook.approved?.source
        ? `Approved scene plate · ${sceneLook.approved.source}`
        : "Current scene plate";
    return `<section class="keyframe-source-panel">
      <div class="source-panel-head">
        <div><span>Scene plate</span><strong>Choose the world plate before keyframe work</strong></div>
        <em>${esc(assetItems.length ? `${assetItems.length} assets` : "Ready")}</em>
      </div>
      <p>Use a reusable location, house or scene asset as the scene plate source, fire a fresh plate, or upload your own. This is separate from approving the current keyframe.</p>
      ${scenePlateUrl ? `<div class="scene-plate-current">
        <img src="${esc(scenePlateUrl)}?v=${Date.now()}" alt="Current scene plate">
        <div><span>${esc(scenePlateLabel)}</span><strong>${esc(sceneLook.plateHash ? sceneLook.plateHash.slice(0, 12) : "scene plate")}</strong></div>
      </div>` : `<div class="source-empty">No current scene plate preview available.</div>`}
      <div class="source-actions">
        <button type="button" class="secondary" data-toggle-scene-plate-library="">${esc(app.scenePlateLibraryOpen ? "Hide Library" : "From Library")}</button>
        <button type="button" class="secondary" data-fire-scene-plate="">Fire Scene Plate</button>
        <label class="secondary">
          Upload Scene Plate
          <input type="file" accept="image/png,image/jpeg,image/webp" data-scene-plate-upload>
        </label>
      </div>
      ${app.scenePlateLibraryOpen ? `<div class="source-library-row asset-library-row">
        ${app.sceneAssetLibraryLoading || !app.sceneAssetLibrary
          ? `<div class="source-empty">Loading scene and house library...</div>`
          : assetError
            ? `<div class="source-empty error">${esc(assetError)}</div>`
            : assetItems.length
              ? assetItems.slice(0, 24).map((item) => `<article class="source-library-card scene-asset">
                <img src="${esc(item.url)}" alt="${esc(item.title)}">
                <div><strong>${esc(item.title)}</strong><em>${esc(item.type)} · ${esc(item.subtitle || "")}</em></div>
                <button type="button" data-select-scene-plate-asset="${esc(item.path)}">Use as Plate</button>
              </article>`).join("")
              : `<div class="source-empty">No scene or house library assets found.</div>`}
      </div>` : ""}
      <div class="source-panel-head">
        <div><span>Keyframe source</span><strong>Generate, previous keyframe, or upload</strong></div>
        <em>${esc(locked ? "Review candidate first" : "Ready")}</em>
      </div>
      <p>${esc(sourceMessage)}</p>
      <div class="source-actions">
        <label class="secondary ${locked ? "disabled" : ""}">
          Upload Keyframe
          <input type="file" accept="image/png,image/jpeg,image/webp" data-keyframe-upload ${locked ? "disabled" : ""}>
        </label>
        <button type="button" class="secondary" data-refresh-keyframe-library>Refresh Library</button>
      </div>
      <div class="source-library-row">
        ${!libraryReady || app.keyframeLibraryLoading
          ? `<div class="source-empty">Loading keyframe library...</div>`
          : app.keyframeLibrary?.error
            ? `<div class="source-empty error">${esc(app.keyframeLibrary.error)}</div>`
            : items.length
              ? items.slice(0, 6).map((item, index) => `<article class="source-library-card">
                ${item.url ? `<img src="${esc(item.url)}?v=${Date.now()}" alt="Keyframe library item">` : `<span>No preview</span>`}
                <div><strong>${esc(item.outcome || "Library item")}</strong><em>${esc(item.at || item.note || `Option ${index + 1}`)}</em></div>
                <button type="button" data-select-keyframe-library="${esc(item.path)}" ${locked ? "disabled" : ""}>Use</button>
              </article>`).join("")
              : `<div class="source-empty">No prior keyframes for this shot yet.</div>`}
      </div>
    </section>`;
  }

  function renderDirectorChecks(beat) {
    const checks = (beat.checklist || []).map((title, index) => [
      title,
      index === 0 ? beat.visibleProof : beat.camera || beat.actionPath,
      !(beat.reviewStatus === "weak" && index === Math.min(2, (beat.checklist || []).length - 1)),
    ]);
    return checks.map(([title, copy, pass]) => `<li class="${pass ? "pass" : "warn"}">
      <span>${pass ? "✓" : "!"}</span>
      <div><strong>${esc(title)}</strong><p>${esc(copy)}</p></div>
    </li>`).join("");
  }

  function renderStageComms(session) {
    const comms = session.stageComms;
    if (!comms) return "";
    const visible = comms.artifactVisible ? "Result visible" : "No visible result";
    return `<section class="stage-comms ${esc(comms.severity || "info")}" role="status" aria-live="polite">
      <div><span>${esc(visible)}</span><strong>${esc(comms.title || "Stage update")}</strong></div>
      <p>${esc(comms.message || "")}</p>
      ${comms.nextAction ? `<em>${esc(comms.nextAction)}</em>` : ""}
    </section>`;
  }

  function artifactPreview(session, beat) {
    if (session.status === "rendering") return renderProgress(session);
    if (session.spendDisclosure && (session.decisionActions || []).some((action) => action.id === "approve-spend")) {
      const spend = session.spendDisclosure;
      return `<div class="render-ready-panel" role="status" aria-live="polite">
        <span class="render-kicker">Request sealed</span>
        <h3>Ready to render ${esc(spend.resolution || "480p")}</h3>
        <p>No video is rendering yet. The exact prompt, opening frame, turnarounds, scene plate and approved voice are locked to this request.</p>
        <div class="render-ready-meta">
          <span>${esc(spend.providerModelId || session.providerModel || "Seedance")}</span>
          <span>${esc(Number(spend.shotDurationSec || session.shot?.durationSec || 0))}s</span>
          <span>${esc(spend.candidateCount || 1)} candidate</span>
          <span>max $${Number(spend.maxBatchCostUsd || 0).toFixed(2)}</span>
        </div>
      </div>`;
    }
    const artifact = session.artifact || {};
    if (artifact.type === "image" && artifact.url) {
      return `<div class="workbench-artifact-frame">
        <span>${esc(artifact.label || beat.keyframe || "Current keyframe")}</span>
        <img src="${esc(artifact.url)}?v=${Date.now()}" alt="${esc(artifact.label || "Current keyframe candidate")}">
      </div>`;
    }
    if (artifact.type === "audio" && artifact.url) {
      const selectedShot = (session.shots || []).find((shot) => shot.selected) || {};
      const keyframeUrl = selectedShot.keyframeUrl || "";
      return `<div class="workbench-artifact-frame voice">
        ${keyframeUrl ? `<figure>
          <span>Approved opening keyframe</span>
          <img src="${esc(keyframeUrl)}?v=${Date.now()}" alt="Approved opening keyframe for this shot">
        </figure>` : `<figure class="missing">
          <span>No keyframe visible</span>
          <strong>The voice take exists, but no approved keyframe URL is available for this shot.</strong>
        </figure>`}
        <div class="workbench-voice-player">
          <span>${esc(artifact.label || "Voice performance")}</span>
          <strong>Voice review active. Approve or refire the dialogue performance only.</strong>
          <audio controls preload="metadata" src="${esc(artifact.url)}?v=${Date.now()}"></audio>
        </div>
      </div>`;
    }
    if (artifact.type === "video" && artifact.url) {
      return `<div class="workbench-artifact-frame">
        <span>${esc(artifact.label || "Current animation")}</span>
        <video controls playsinline preload="metadata" src="${esc(artifact.url)}?v=${Date.now()}"></video>
      </div>`;
    }
    if (artifact.type === "video-set" && (artifact.items || []).length) {
      const item = artifact.items[0];
      return `<div class="workbench-artifact-frame">
        <span>${esc(artifact.label || "Animation candidate")}</span>
        <video controls playsinline preload="metadata" src="${esc(item.url)}?v=${Date.now()}"></video>
      </div>`;
    }
    return `<div class="workbench-beat-frame ${esc(beat.id)}">
      <span>${esc(beat.shot)} • ${esc(beat.range)} • ${esc(beat.priority)} beat</span>
      <strong>${esc(beat.keyframe)}</strong>
      <p>${esc(beat.startState)}</p>
      <em>${esc(beat.actionPath)}</em>
    </div>`;
  }

  function workbenchGateState(session) {
    const activeGate = ["voice", "animation"].includes(session.phase)
      ? "Generate"
      : session.phase === "review" || session.phase === "final"
        ? "Review"
        : session.phase === "story"
          ? "Direction"
          : "Keyframes";
    const completed = activeGate === "Generate" ? 3 : activeGate === "Review" ? 4 : activeGate === "Direction" ? 1 : 2;
    const next = activeGate === "Keyframes"
      ? "Approve the active beat keyframe before Generate unlocks."
      : activeGate === "Generate"
        ? session.phase === "voice"
          ? "Create or approve the voice performance, then generate footage."
          : "Generate and review the draft animation."
        : activeGate === "Review"
          ? "Approve delivered beats or create targeted fixes."
          : "Complete direction before keyframes.";
    return { activeGate, completed, total: sceneOneContract.gates.length, next };
  }

  function relayStage(session) {
    if (session.phase === "keyframe" || session.phase === "story") return 1;
    if (session.phase === "voice") return 2;
    return 3;
  }

  function selectedShotSummary(session) {
    return (session.shots || []).find((shot) => shot.selected) ||
      (session.shots || []).find((shot) => shot.shotId === session.selectedShotId) || {};
  }

  function audioWaveformMarkup(label = "Approved audio") {
    const heights = [22, 38, 54, 31, 68, 44, 76, 58, 34, 63, 81, 48, 72, 39, 60, 29, 51, 69, 43, 57, 33, 46, 25];
    return `<div class="audio-waveform" role="img" aria-label="${esc(label)} waveform">
      <span class="audio-waveform-mark" aria-hidden="true"></span>
      <div aria-hidden="true">${heights.map((height) => `<i style="--wave-height:${height}%"></i>`).join("")}</div>
    </div>`;
  }

  function relayMedia(stage, session) {
    const selected = selectedShotSummary(session);
    const artifact = session.artifact || {};
    if (stage === 1) {
      const url = session.phase === "keyframe" && artifact.type === "image" ? artifact.url : selected.keyframeUrl;
      return url ? `<button type="button" class="relay-keyframe-preview" data-keyframe-preview="${esc(url)}" aria-label="Enlarge keyframe" title="Enlarge keyframe">
        <img src="${esc(url)}" alt="Shot keyframe for sign-off">
        <span>View full size</span>
      </button>` : `<div class="relay-empty">No keyframe has been created yet.</div>`;
    }
    if (stage === 2) {
      const url = session.phase === "voice" && artifact.type === "audio" ? artifact.url : selected.voiceUrl;
      return url ? `<div class="relay-audio-player">${audioWaveformMarkup("Approved voice performance")}<audio controls preload="metadata" src="${esc(url)}"></audio></div>` : `<div class="relay-empty">Voice is locked until SEE is approved.</div>`;
    }
    const videoUrl = artifact.type === "video" ? artifact.url :
      artifact.type === "video-set" ? artifact.items?.[0]?.url : selected.acceptedUrl;
    if (videoUrl) return `<video controls playsinline preload="metadata" src="${esc(videoUrl)}"></video>`;
    return `<div class="relay-empty">${session.phase === "animation" ? "No video has been submitted yet. The approved frame and voice are ready for the 480p render." : "Animation is locked until SEE and HEAR are approved."}</div>`;
  }

  function relayCard(stage, session) {
    const active = relayStage(session);
    const names = { 1: "SEE", 2: "HEAR", 3: "WATCH" };
    const descriptions = {
      1: "Approve the exact stage and opening composition.",
      2: "Approve the dialogue performance and timing.",
      3: "Approve the 480p animation result.",
    };
    const locked = stage > active;
    const complete = stage < active || session.status === "complete";
    const current = stage === active && !complete;
    const actions = [session.primaryAction, ...(session.decisionActions || [])].filter(Boolean);
    const accept = current ? actions.find((action) => action.id.startsWith("accept-")) : null;
    const iterate = current ? actions.find((action) => action.id.startsWith("iterate-") || action.id === "reopen-shot") : null;
    const primary = current ? (accept || session.primaryAction || actions.find((action) => action.id === "approve-spend")) : null;
    const stateLabel = locked ? "Locked" : complete ? "Signed" : session.status === "rendering" ? "Working" : session.status === "ready_to_review" ? "Your decision" : "Ready";
    const savedNote = session.savedRetakeNotes?.[`${session.selectedShotId}:${stage}`] || "";
    return `<article class="relay-card ${current ? "current" : ""} ${locked ? "locked" : ""} ${complete ? "complete" : ""}">
      <header><span>${stage}</span><div><strong>${names[stage]}</strong><p>${descriptions[stage]}</p></div><em>${stateLabel}</em></header>
      <div class="relay-media">${relayMedia(stage, session)}</div>
      ${locked ? `<p class="relay-lock">Complete ${names[stage - 1]} before this sign-off unlocks.</p>` : `
        ${stage === 1 && current ? `<details class="relay-source-drawer">
          <summary>Choose scene plate or keyframe source</summary>
          ${renderKeyframeSourcePanel(session)}
        </details>` : ""}
        <label class="relay-notes">Retake notes<textarea data-relay-note="${stage}" placeholder="What needs to change? Plain English is enough.">${esc(savedNote)}</textarea><span class="relay-note-status" data-relay-note-status="${stage}">${savedNote ? "Saved" : ""}</span></label>
        <div class="relay-actions">
          ${primary ? `<button type="button" class="primary" data-relay-action="${esc(primary.id)}">${esc(primary.id === "direct-scene" ? "Start scene → generate keyframes" : primary.label)}</button>` : complete ? `<span>Approved</span>` : ""}
          ${iterate ? `<button type="button" class="secondary danger" data-relay-retake="${esc(iterate.id)}" data-relay-stage="${stage}">Refire with notes</button>` : ""}
        </div>`}
    </article>`;
  }

  function renderSignoffRelay(session) {
    const host = $("#scene-workbench");
    if (!host) return;
    const mediaState = Array.from(host.querySelectorAll("audio,video")).map((media) => ({
      src: media.currentSrc || media.src,
      currentTime: Number.isFinite(media.currentTime) ? media.currentTime : 0,
      paused: media.paused,
      muted: media.muted,
      volume: media.volume,
    }));
    const sceneTotal = app.directorBoard?.sceneCount || rosterScenes().length || 1;
    const selected = selectedShotSummary(session);
    const shotNumber = selected.number || 1;
    const stage = relayStage(session);
    host.innerHTML = `<div class="relay-orientation">Scene ${esc(session.scene)} of ${sceneTotal} · Shot ${shotNumber} · Sign-off ${stage} of 3</div>
      <div class="workbench-top relay-heading">
        <div><span class="stage-label">${esc(session.sceneName || `Scene ${session.scene}`)}</span><h2>${esc(session.selectedShotId || "Scene direction")}</h2><p>${esc(session.shot?.purpose || session.summary || "")}</p></div>
        <span class="workbench-status ${esc(session.phase)}">${esc(session.status === "ready_to_review" ? "YOUR DECISION" : session.status === "rendering" ? "WORKING" : "READY")}</span>
      </div>
      ${renderStageComms(session)}
      ${renderRecentFailure(session)}
      ${renderGenerateStatus(session)}
      <section class="relay-grid">${[1, 2, 3].map((item) => relayCard(item, session)).join("")}</section>`;
    host.querySelectorAll("audio,video").forEach((media) => {
      const prior = mediaState.find((item) => item.src === (media.currentSrc || media.src));
      if (!prior) return;
      const restore = () => {
        if (prior.currentTime > 0 && Math.abs(media.currentTime - prior.currentTime) > 0.25) {
          media.currentTime = Math.min(prior.currentTime, Number.isFinite(media.duration) ? media.duration : prior.currentTime);
        }
        media.muted = prior.muted;
        media.volume = prior.volume;
        if (!prior.paused) media.play().catch(() => {});
      };
      if (media.readyState >= 1) restore(); else media.addEventListener("loadedmetadata", restore, { once: true });
    });
    host.querySelectorAll("[data-keyframe-preview]").forEach((button) => button.addEventListener("click", () => {
      openKeyframePreview(button.dataset.keyframePreview);
    }));
    host.querySelectorAll("[data-relay-action]").forEach((button) => button.addEventListener("click", () => {
      const actions = [app.session?.primaryAction, ...(app.session?.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.relayAction);
      if (!action) return toast("That decision changed. Refreshing current state.", true), loadSession();
      button.disabled = true;
      handleAction(action);
    }));
    host.querySelectorAll("[data-relay-retake]").forEach((button) => button.addEventListener("click", () => {
      const note = host.querySelector(`[data-relay-note="${button.dataset.relayStage}"]`)?.value.trim();
      if (!note) return toast("Write the retake diagnosis first.", true);
      const actions = [app.session?.primaryAction, ...(app.session?.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.relayRetake);
      if (!action) return toast("That retake action changed. Refreshing current state.", true), loadSession();
      button.disabled = true;
      submitAction(action, note);
    }));
    host.querySelectorAll("[data-relay-note]").forEach((textarea) => {
      textarea.addEventListener("input", () => {
        clearTimeout(relayNoteTimers.get(textarea));
        const status = document.querySelector(`[data-relay-note-status="${textarea.dataset.relayNote}"]`);
        if (status) status.textContent = "Unsaved changes";
        relayNoteTimers.set(textarea, setTimeout(() => saveRelayNote(textarea), 500));
      });
      textarea.addEventListener("change", () => saveRelayNote(textarea));
      textarea.addEventListener("blur", () => saveRelayNote(textarea));
    });
    host.querySelectorAll("[data-dismiss-failure]").forEach((button) => button.addEventListener("click", () => {
      localStorage.setItem(`dismissed-failure:${button.dataset.dismissFailure}`, "1");
      button.closest(".relay-failure")?.remove();
    }));
    host.querySelectorAll("[data-retry-failure]").forEach((button) => button.addEventListener("click", () => {
      const actions = [app.session?.primaryAction, ...(app.session?.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.retryFailure);
      if (!action) return toast("That fix is no longer current. Refreshing current state.", true), loadSession();
      button.disabled = true;
      handleAction(action);
    }));
    host.querySelectorAll("[data-refresh-keyframe-library]").forEach((button) => button.addEventListener("click", async () => {
      app.keyframeLibraryKey = null;
      await loadKeyframeLibrary(app.session || session);
      renderSignoffRelay(app.session || session);
    }));
    host.querySelectorAll("[data-select-keyframe-library]").forEach((button) => button.addEventListener("click", () => {
      selectKeyframeFromLibrary(button.dataset.selectKeyframeLibrary);
    }));
    host.querySelectorAll("[data-toggle-scene-plate-library]").forEach((button) => button.addEventListener("click", () => {
      app.scenePlateLibraryOpen = !app.scenePlateLibraryOpen;
      renderSignoffRelay(app.session || session);
    }));
    host.querySelectorAll("[data-fire-scene-plate]").forEach((button) => button.addEventListener("click", () => {
      runScenePlateAction("build-scene-plate");
    }));
    host.querySelectorAll("[data-select-scene-plate-asset]").forEach((button) => button.addEventListener("click", () => {
      runScenePlateAction("select-scene-plate-library", button.dataset.selectScenePlateAsset);
    }));
    host.querySelectorAll("[data-keyframe-upload]").forEach((input) => input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file) uploadKeyframeSource(file);
      input.value = "";
    }));
    host.querySelectorAll("[data-scene-plate-upload]").forEach((input) => input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file) uploadScenePlateSource(file);
      input.value = "";
    }));
  }

  function renderRecentFailure(session) {
    const failure = session.recentFailure;
    if (!failure?.jobId || localStorage.getItem(`dismissed-failure:${failure.jobId}`)) return "";
    const fix = session.primaryAction;
    return `<div class="relay-failure" role="alert"><div><strong>Last action failed</strong><p>${esc(failure.error || "The provider did not return a usable result.")}</p></div><div class="relay-failure-actions">${fix ? `<button type="button" class="primary" data-retry-failure="${esc(fix.id)}">${esc(fix.label || "Retry")}</button>` : ""}<button type="button" class="secondary" data-dismiss-failure="${esc(failure.jobId)}">Dismiss</button></div></div>`;
  }

  async function saveRelayNote(textarea) {
    const stage = textarea.dataset.relayNote;
    const status = document.querySelector(`[data-relay-note-status="${stage}"]`);
    if (status) status.textContent = "Saving...";
    try {
      await api("/api/director-action", {
        method: "POST",
        body: JSON.stringify({
          action: "save-retake-note", episode: app.episode, scene: app.scene,
          shotId: app.session?.selectedShotId, stage, note: textarea.value.trim(),
        }),
      });
      if (status) status.textContent = "Saved";
      if (app.session) {
        app.session.savedRetakeNotes ||= {};
        app.session.savedRetakeNotes[`${app.session.selectedShotId}:${stage}`] = textarea.value.trim();
      }
    } catch (error) {
      if (status) status.textContent = `Not saved: ${error.message}`;
      toast(`Director note not saved: ${error.message}`, true);
    }
  }

  function renderSceneWorkbench(session) {
    const host = $("#scene-workbench");
    if (!host) return;
    const beat = displayBeatState(currentBeat(), session);
    const beats = workbenchBeats().map((item) => displayBeatState(item, session));
    const primary = workbenchPrimaryAction(session, beat);
    const gateState = workbenchGateState(session);
    const gates = sceneOneContract.gates.map((gate, index) => {
      const active = (session.phase === "keyframe" && gate === "Keyframes") || (["voice", "animation"].includes(session.phase) && gate === "Generate") || (session.phase === "review" && gate === "Review");
      const complete = index < 2 || (gate === "Keyframes" && ["voice", "animation", "review", "final"].includes(session.phase));
      return `<button type="button" class="${active ? "active" : complete ? "complete" : ""}" data-workbench-gate="${esc(gate.toLowerCase())}">
        <span>${complete ? "✓" : index + 1}</span>${esc(gate)}
      </button>`;
    }).join("");
    host.innerHTML = `<div class="workbench-top">
      <div>
        <span class="stage-label">Crystal Bears / Episode 1 / Scene 1</span>
        <h2>${esc(sceneOneContract.title)}</h2>
        <p>${esc(sceneOneContract.promise)}</p>
      </div>
      <span class="workbench-status ${esc(session.phase || beat.reviewStatus)}">${esc(workbenchStatusLabel(session, beat))}</span>
    </div>
    <nav class="workbench-gates" aria-label="Scene workflow">${gates}<div class="workbench-gate-summary"><strong>${gateState.completed} / ${gateState.total}</strong><span>${esc(gateState.activeGate)} active</span><em>${esc(gateState.next)}</em></div></nav>
    <div class="workbench-grid">
      <aside class="beat-panel">
        <div class="panel-title"><strong>Story / Beats</strong><span>${beats.length}</span></div>
        ${beats.map((item) => `<button type="button" class="beat-card ${item.id === beat.id ? "selected" : ""} ${item.reviewStatus}" data-beat="${esc(item.id)}">
          <span class="beat-number">${item.n}</span>
          <div><strong>${esc(item.title)}</strong><p>${esc(item.intent)}</p>${item.id === beat.id ? `<dl><dt>Active beat</dt><dd>${esc(item.range)} · ${esc(statusLabel(item.reviewStatus))}</dd><dt>Visible proof</dt><dd>${esc(item.visibleProof)}</dd><dt>Fail conditions</dt><dd>${esc((item.failConditions || []).join("; "))}</dd></dl>` : ""}</div>
          <em>${esc(item.id === beat.id ? `Active · ${item.priority}` : item.priority)}</em>
        </button>`).join("")}
      </aside>
      <section class="keyframe-studio">
        <div class="panel-title workbench-panel-title"><div><strong>${esc(["voice", "animation"].includes(session.phase) ? "Generate Studio" : `Keyframe Studio — ${beat.title}`)}</strong><p>Shot: ${esc(beat.shot)} • ${esc(beat.range)} • ${esc(beat.priority)} beat</p></div><span>${esc(beat.keyframe)}</span></div>
        <div class="workbench-canvas">
          ${artifactPreview(session, beat)}
        </div>
        ${beat.secondaryKeyframe ? `<div class="keyframe-substates"><button type="button" class="active">${esc(beat.keyframe)}</button><button type="button">${esc(beat.secondaryKeyframe)}</button></div>` : ""}
        <div class="workbench-ref-row">${renderWorkbenchRefs(session)}</div>
        ${renderKeyframeSourcePanel(session)}
        <details class="builder-details" data-prompt-copy-panel>
          <summary><span>Builder Mode · prompt segment and reference roles</span><span class="prompt-copy-actions"><span class="prompt-copy-status" data-copy-prompt-status aria-live="polite"></span><button type="button" class="prompt-copy-button" data-copy-prompt aria-label="Copy prompt" title="Copy prompt"><span aria-hidden="true"></span></button></span></summary>
          <pre>${esc(beat.promptSegment || requestPromptText(session))}</pre>
        </details>
      </section>
      <aside class="director-check-panel">
        <div class="panel-title"><strong>${esc(session.phase === "voice" ? "Voice Check" : "Director Check")}</strong><span>${esc(workbenchPanelStatusLabel(session, beat))}</span></div>
        <ul class="director-check-list">${renderDirectorChecks(beat)}</ul>
        ${renderStageComms(session)}
        <div class="visual-proof-card"><span>Visual Proof</span><p>${esc(beat.visibleProof)}</p></div>
        ${beat.recommendedFix ? `<div class="visual-proof-card warning"><span>Recommended Fix</span><p>${esc(beat.recommendedFix)}</p></div>` : ""}
        ${renderGenerateStatus(session)}
        <div class="workbench-actions">
          ${primary ? `<button type="button" class="primary" data-workbench-action="${esc(primary.action.id)}">${esc(primary.label)}</button>` : ""}
          ${session.decisionActions?.some((action) => action.id.startsWith("iterate-")) ? `<button type="button" class="secondary danger" data-workbench-action="${esc(session.decisionActions.find((action) => action.id.startsWith("iterate-")).id)}">Refire</button>` : ""}
        </div>
      </aside>
    </div>
    <section class="generation-review-strip">
      <div><strong>Generation + Review</strong><span>${esc(beat.range)} · ${esc(beat.title)} · ${esc(workbenchPanelStatusLabel(session, beat))}</span></div>
      <div class="review-timeline">${beats.map((item) => `<button type="button" class="${item.id === beat.id ? "active" : ""} ${item.reviewStatus}" data-beat="${esc(item.id)}"><span>${esc(item.title)}</span></button>`).join("")}</div>
      <p>${esc(beat.reviewNote || beat.visibleProof)}</p>
    </section>`;
    bindPromptCopyButtons(host);
    host.querySelectorAll("[data-beat]").forEach((button) => button.addEventListener("click", () => {
      app.activeBeatId = button.dataset.beat;
      app.explicitBeat = true;
      writeHash();
      saveProjectWorkbenchState();
      renderSceneWorkbench(app.session || session);
    }));
    host.querySelectorAll("[data-workbench-action]").forEach((button) => button.addEventListener("click", () => {
      const actions = [app.session?.primaryAction, ...(app.session?.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.workbenchAction);
      if (!action) {
        toast("This action is no longer current. Refreshing the shot status...", true);
        loadSession();
        return;
      }
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.textContent = action.id === "prepare-render" ? "Preparing render..." : "Working...";
      handleAction(action);
    }));
    host.querySelectorAll("[data-workbench-gate]").forEach((button) => button.addEventListener("click", () => {
      const gate = button.dataset.workbenchGate;
      const stepByGate = {
        script: "upload",
        direction: "storyboard",
        keyframes: "storyboard",
        generate: session.phase === "voice" ? "audio" : "footage",
        review: "rough-cut",
      };
      app.pipelineStep = stepByGate[gate] || livePipelineStep(session);
      setView("pipeline");
      renderPipeline();
    }));
    host.querySelectorAll("[data-refresh-keyframe-library]").forEach((button) => button.addEventListener("click", () => {
      app.keyframeLibraryKey = null;
      loadKeyframeLibrary(app.session || session);
    }));
    host.querySelectorAll("[data-select-keyframe-library]").forEach((button) => button.addEventListener("click", () => {
      selectKeyframeFromLibrary(button.dataset.selectKeyframeLibrary);
    }));
    host.querySelectorAll("[data-toggle-scene-plate-library]").forEach((button) => button.addEventListener("click", () => {
      app.scenePlateLibraryOpen = !app.scenePlateLibraryOpen;
      renderSceneWorkbench(app.session || session);
    }));
    host.querySelectorAll("[data-fire-scene-plate]").forEach((button) => button.addEventListener("click", () => {
      runScenePlateAction("build-scene-plate");
    }));
    host.querySelectorAll("[data-select-scene-plate-asset]").forEach((button) => button.addEventListener("click", () => {
      runScenePlateAction("select-scene-plate-library", button.dataset.selectScenePlateAsset);
    }));
    host.querySelectorAll("[data-keyframe-upload]").forEach((input) => input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file) uploadKeyframeSource(file);
      input.value = "";
    }));
    host.querySelectorAll("[data-scene-plate-upload]").forEach((input) => input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file) uploadScenePlateSource(file);
      input.value = "";
    }));
    loadKeyframeLibrary(session);
    loadSceneAssetLibrary();
  }

  function directorActionLabel(action) {
    if (!action) return "";
    return action.id === "approve-spend"
      ? "Render 480p"
      : action.id === "accept-keyframe" ? "Approve Keyframe"
      : action.id === "accept-voice" ? "Approve Voice"
      : action.id === "accept-animation" ? "Approve Animation"
      : action.id === "iterate-keyframe" ? "Refire Keyframe"
      : action.id === "iterate-voice" ? "Refire Voice"
      : action.id === "iterate-animation" ? "Refire Animation"
      : action.id.startsWith("accept-") ? "Approve" : action.id.startsWith("iterate-") ? "Refire" : action.label;
  }

  function actionButton(action, kind) {
    const className = kind === "primary" ? "primary" : `secondary${action.destructive ? " danger" : ""}`;
    const label = directorActionLabel(action);
    const active = app.localActivity &&
      app.localActivity.state !== "held" &&
      app.localActivity.shotId === app.session?.selectedShotId;
    return `<button type="button" class="${className}" data-action="${esc(action.id)}" ${active ? "disabled" : ""}>${esc(active ? "Working..." : label)}</button>`;
  }

  function actionGuidance(session) {
    const action = session.primaryAction || (session.decisionActions || [])[0] || {};
    const byAction = {
      "build-keyframe": {
        now: "Opening frame",
        outcome: "Creates one keyframe candidate for this shot.",
        next: "Review the image, then Approve or Refire.",
        guard: "No animation render is submitted at this stage.",
      },
      "direct-scene": {
        now: "Scene direction",
        outcome: "Creates the production shots for this scene from the locked script.",
        next: "Then pick the first shot, build its keyframe, approve or iterate, and continue.",
        guard: "You can do this out of order; continuity warnings stay visible when a prior scene is unfinished.",
      },
      "accept-keyframe": {
        now: "Keyframe review",
        outcome: "Locks this image as the stage truth.",
        next: "Create the dialogue performance, then prepare animation.",
        guard: "Approve only if the character scale, staging and open action space are right.",
      },
      "iterate-keyframe": {
        now: "Keyframe review",
        outcome: "Rejects this candidate and asks for a corrected opening frame.",
        next: "A new keyframe candidate will come back for review.",
        guard: "Use this when identity, scale, staging or action room is wrong.",
      },
      "build-voice": {
        now: "Voice",
        outcome: "Creates the approved ElevenLabs dialogue performance.",
        next: "Review the audio, then Approve or Refire.",
        guard: "This is dialogue only; music belongs after footage is stitched.",
      },
      "accept-voice": {
        now: "Voice review",
        outcome: "Locks the dialogue performance for animation.",
        next: "Prepare the Seedance animation request.",
        guard: "Approve only if timing, speaker ownership and acting cadence are right.",
      },
      "iterate-voice": {
        now: "Voice review",
        outcome: "Rejects this take and asks for a corrected performance.",
        next: "A new dialogue take will come back for review.",
        guard: "Use this for timing, cadence, wrong speaker or audio glitches.",
      },
      "prepare-render": {
        now: "Animation setup",
        outcome: "Builds the exact Seedance request for this shot.",
        next: "Review cost, references and prompt before pressing Render.",
        guard: "No video spend happens until render approval.",
      },
      "approve-spend": {
        now: "Animation render",
        outcome: "Submits the approved Seedance request at 480p.",
        next: "Watch the result, then Approve or Refire.",
        guard: "This is the paid render step.",
      },
      "accept-animation": {
        now: "Animation review",
        outcome: "Accepts this clip into the episode sequence.",
        next: "Move to the next shot or rough cut when all shots are accepted.",
        guard: "Approve only if the beat lands on screen.",
      },
      "iterate-animation": {
        now: "Animation review",
        outcome: "Rejects this clip and prepares a corrected render request.",
        next: "Review the corrected prompt/cost before rendering again.",
        guard: "Use this when the shot misses the beat, staging, continuity or performance.",
      },
    };
    const guide = byAction[action.id] || {
      now: phaseLabel(session.phase),
      outcome: session.headline || "Continue the current production step.",
      next: "The next available outcome will appear here.",
      guard: "The Studio will keep the current shot state visible.",
    };
    return `<div class="action-guidance" aria-label="Current workflow guidance">
      <span>${esc(guide.now)}</span>
      <strong>${esc(guide.outcome)}</strong>
      <p>${esc(guide.next)}</p>
      <em>${esc(guide.guard)}</em>
    </div>`;
  }

  function renderActions(session) {
    const host = $("#action-area");
    if (session.status === "rendering") {
      host.innerHTML = `${actionGuidance(session)}${renderGenerateStatus(session)}<button type="button" class="primary" disabled>Working...</button>`;
      return;
    }
    const status = renderGenerateStatus(session);
    if ((session.decisionActions || []).length) {
      host.innerHTML = `${actionGuidance(session)}${status}<div class="decision-set">${session.decisionActions.map((action, index) => actionButton(action, index === 0 ? "primary" : "secondary")).join("")}</div>`;
    } else if (session.primaryAction) {
      host.innerHTML = `${actionGuidance(session)}${status}${actionButton(session.primaryAction, "primary")}`;
    } else {
      host.innerHTML = status;
    }
    host.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => {
      const actions = [session.primaryAction, ...(session.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === button.dataset.action);
      if (action) handleAction(action);
    }));
  }

  function renderDirector(session) {
    const legacyOutcome = document.querySelector(".director-outcome");
    if (legacyOutcome) legacyOutcome.hidden = true;
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
    renderAdvisories(session);
    $("#save-state").textContent = session.lineageCurrent ? "Current" : "Needs refresh";
    $("#references-button").disabled = !session.selectedShotId;
    $("#request-button").disabled = !session.inspector?.providerRequest;
    $("#truth-note").textContent = session.inspector?.structuralClaim || "Creative quality is judged from the result.";
    const inspectorUrl = `/cb-studio/app.html#p=crystal-bears&pg=pipeline&ep=${encodeURIComponent(session.episode)}&sc=${encodeURIComponent(session.scene)}&st=${encodeURIComponent(session.phase)}${session.selectedShotId ? `&shot=${encodeURIComponent(session.selectedShotId)}` : ""}`;
    $("#full-inspector-link").href = inspectorUrl;
    $("#drawer-inspector-link").href = inspectorUrl;
    renderDirectorSceneStrip(session);
    renderShotSwitcher(session);
    renderSignoffRelay(session);
    renderArtifact(session);
    renderShotInputs(session);
    renderActions(session);
    loadInlineShotContext(session);
  }

  function renderEpisodes() {
    const scenes = app.roster?.scenes || [];
    const boardScenes = app.directorBoard?.scenes || [];
    const completed = boardScenes.filter((scene) => scene.status === "complete").length;
    $("#episode-progress-label").textContent = `${completed} of ${scenes.length} scenes complete · ${app.directorBoard?.queue?.length || 0} decisions waiting`;
    $("#episode-progress-bar").style.width = `${Math.max(2, (completed / Math.max(1, scenes.length)) * 100)}%`;
    $("#scene-list").innerHTML = scenes.map((scene) => {
      const number = String(scene.sceneNumber);
      const current = number === app.scene;
      const board = boardScenes.find((item) => String(item.scene) === number) || {};
      return `<button type="button" class="scene-row ${current ? "current" : ""}" data-scene="${esc(number)}">
        <span class="scene-number">${String(scene.sceneNumber).padStart(2, "0")}</span>
        <span class="scene-copy"><strong>${esc(scene.location || `Scene ${number}`)}</strong><span>${esc(scene.time || "")} · ${scene.beatCount || 0} story beats${board.shotCount ? ` · ${board.completeShots || 0}/${board.shotCount} shots` : ""}</span></span>
        <span class="scene-status ${esc(board.status || "untouched")}">${esc(board.started ? `${board.statusLabel} · ${board.nextLabel}` : "Start scene → generate keyframes")}</span>
      </button>`;
    }).join("") || '<div class="reference-unavailable">No current scenes.</div>';
    $("#scene-list").querySelectorAll("[data-scene]").forEach((button) => button.addEventListener("click", () => {
      app.scene = button.dataset.scene;
      app.shotId = null;
      resetShotScopedState();
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
    const isReal = Boolean(shot.shotId);
    const shotId = shot.shotId || `demo-${shot.shot}`;
    const selected = isReal && shot.selected;
    const state = isReal ? statusText(shot.state) : shot.status;
    const title = isReal ? shot.shotId : shot.title;
    const characters = isReal
      ? (selected ? app.session?.shot?.characters || [] : [])
      : shot.characters;
    const purpose = isReal ? shot.purpose || "" : shot.setup || "";
    const imageUrl = isReal ? (shot.keyframeUrl || shot.acceptedUrl || "") : "";
    const pipeline = isReal ? shotPipelineRail(shot) : "";
    const nextAction = selected
      ? (app.session?.primaryAction?.label || (app.session?.decisionActions || [])[0]?.label || "Open Shot")
      : "Open Shot";
    return `<article class="storyboard-shot ${selected ? "selected" : ""} ${shot.state === "complete" ? "ready" : ""}">
      <div class="storyboard-frame ${imageUrl ? "has-media" : ""}" aria-label="${esc(title)} image">
        ${imageUrl ? `<img src="${esc(imageUrl)}?v=${Date.now()}" alt="${esc(title)}">` : `<span>${esc(title)}</span>`}
        <div class="storyboard-tags">${characters.map((character) => `<b>${esc(character)}</b>`).join("")}</div>
      </div>
      <div class="storyboard-shot-copy">
        <div class="storyboard-shot-head">
          <strong>Shot ${esc(isReal ? (shot.number || shotId) : shot.shot)}</strong>
          <span class="status-pill ${shot.state === "complete" ? "ok" : selected ? "ok" : ""}">${esc(state)}</span>
        </div>
        ${purpose ? `<p>${esc(purpose)}</p>` : ""}
        ${pipeline}
        <div class="storyboard-ref-label">References · complete turnarounds and scene look stay locked</div>
        <div class="storyboard-ref-row"><span>Scene</span><span>Character</span><span>Keyframe</span></div>
        ${isReal ? `<button type="button" class="primary" data-production-shot="${esc(shotId)}" data-view-jump="director">${esc(nextAction)}</button>` : '<button type="button" class="secondary" disabled>Demo only</button>'}
      </div>
    </article>`;
  }

  function shotPipelineRail(shot) {
    const selected = shot.selected;
    const currentPhase = selected ? app.session?.phase : null;
    const complete = shot.state === "complete";
    const keyframeDone = Boolean(shot.keyframeUrl || shot.acceptedUrl || complete);
    const animationDone = Boolean(shot.acceptedUrl || complete);
    const steps = [
      { id: "keyframe", label: "Keyframe", done: keyframeDone, active: currentPhase === "keyframe" },
      { id: "voice", label: "Voice", done: selected && ["animation", "review", "final"].includes(currentPhase), active: currentPhase === "voice" },
      { id: "animation", label: "Animation", done: animationDone, active: currentPhase === "animation" },
      { id: "review", label: "Review", done: complete, active: selected && ["review", "final"].includes(currentPhase) },
    ];
    return `<div class="shot-pipeline" aria-label="${esc(shot.shotId)} shot pipeline">
      ${steps.map((step, index) => `<span class="${step.done ? "done" : step.active ? "active" : ""}">
        <i>${step.done ? "✓" : String(index + 1)}</i>${esc(step.label)}
      </span>`).join("")}
    </div>`;
  }

  function renderStoryboardPipeline() {
    const scenes = rosterScenes();
    const scene = currentRosterScene();
    const shots = app.session?.shots || [];
    return `<div class="pipeline-heading-row production-board-head">
      <div><h2>Storyboard</h2><p>${scenes.length || 0} scenes · ${shots.length || 0} current scene shots</p></div>
      <div class="pipeline-model">Keyframes: <strong>Seedream 5 Pro</strong></div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" data-view-jump="director">Open Current Shot</button>
        <button type="button" class="primary" data-next-step="audio">Continue · Audio</button>
      </div>
    </div>
    <section class="production-board">
      <div class="production-board-scenes" aria-label="Episode scenes">
        ${scenes.map((item) => {
          const number = String(item.sceneNumber);
          const open = number === String(app.scene);
          return `<button type="button" data-pipeline-scene="${esc(number)}" class="${open ? "selected" : ""}">
            <span>${esc(number)}</span>
            <strong>${esc(sceneHeading(item))}</strong>
            <em>${Number(item.beatCount || 0)} beats</em>
          </button>`;
        }).join("") || '<span class="production-nav-empty">No approved scenes</span>'}
      </div>
      <div class="storyboard-detail">
        <div class="clip-section-head">
          <div><h3>${esc(sceneHeading(scene))}</h3><span>${shots.length || 0} production shots${scene?.beatCount ? ` / ${Number(scene.beatCount)} story beats` : ""}</span></div>
          <div class="pipeline-actions inline">
            <button type="button" class="secondary" data-view-jump="episodes">Change Scene</button>
            <button type="button" class="primary" data-view-jump="director">${shots.length ? "Work This Scene" : "Direct Scene"}</button>
          </div>
        </div>
        ${shots.length
          ? `<div class="storyboard-shot-grid">${shots.map(renderStoryboardShot).join("")}</div>`
          : `<div class="stage-empty"><p>This scene has not been directed into production shots yet. Open it, press Direct scene, then the shot cards appear here.</p><button type="button" class="primary" data-view-jump="director">Open Scene</button></div>`}
      </div>
    </section>
    <div class="pipeline-footer-actions">
      <button type="button" class="secondary" data-next-step="audio">Audio</button>
      <button type="button" class="secondary" data-next-step="footage">Footage</button>
      <button type="button" class="primary" data-view-jump="director">Current Shot</button>
    </div>`;
  }

  function renderFootagePipeline() {
    const scenes = rosterScenes();
    const scene = currentRosterScene();
    const shots = app.session?.shots || [];
    const candidateItems = app.session?.artifact?.type === "video-set" ? app.session.artifact.items || [] : [];
    return `<div class="pipeline-heading-row">
      <div><h2>Video Clips</h2><p>${shots.length || 0} shots in current scene · 4-30s Seedance units; complex gags split for control</p></div>
      <div class="pipeline-model"><strong>${esc(app.session?.providerModel || "Seedance")}</strong></div>
      <div class="pipeline-actions">
        <button type="button" class="secondary" disabled>Write Prompts with AI</button>
        <button type="button" class="primary" disabled>Generate All Videos · 27,720 tkn · $277.20</button>
      </div>
    </div>
    <div class="jump-row" aria-label="Jump to scene">
      ${scenes.map((item) => {
        const number = String(item.sceneNumber);
        return `<button type="button" data-pipeline-scene="${esc(number)}" class="${number === String(app.scene) ? "selected" : ""}">S${esc(number)} <span>${Number(item.beatCount || 0)} beats</span></button>`;
      }).join("") || '<span class="production-nav-empty">No approved scenes</span>'}
    </div>
    <section class="clip-section">
      <div class="clip-section-head"><h3>Scene ${esc(app.scene)}: ${esc(sceneHeading(scene))}</h3><span>${app.session?.progress?.complete || 0}/${app.session?.progress?.total || 0} accepted</span></div>
      ${candidateItems.length ? renderPipelineArtifact({ id: "footage" }, app.session) : ""}
      ${shots.length ? shots.map((shot) => `<article class="clip-card ${shot.state === "complete" ? "ready" : shot.state === "awaiting" ? "ready" : ""}">
        <div class="clip-card-head">
          <div><h3>${esc(shot.shotId)}</h3><span>${shot.durationSec ? `${Number(shot.durationSec)}s` : "Duration pending"}</span></div>
          <span class="status-pill ${shot.state === "complete" ? "ok" : shot.state === "awaiting" ? "ok" : ""}">${esc(shot.state === "complete" ? "Accepted" : statusText(shot.state))}</span>
        </div>
        ${shot.acceptedUrl ? `<video controls playsinline preload="metadata" src="${esc(shot.acceptedUrl)}"></video>` : ""}
        <label>Shot purpose</label>
        <textarea rows="4" aria-label="${esc(shot.shotId)} purpose" readonly>${esc(shot.purpose || "")}</textarea>
        <div class="generation-meta"><span>${esc(shot.shotId)}</span><span>${esc(app.session?.providerModel || "Seedance")}</span></div>
      </article>`).join("") : footageClips.map((clip) => `<article class="clip-card ${clip.state}">
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
        <div class="track muted"><strong>AUDIO</strong><span>Dialogue + foley from clips</span><span>Scene music in post</span></div>
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
      const recoveryAction = availableActions.find((action) =>
        /voice|performance/i.test(`${action.id} ${action.label}`));
      return `<section class="voice-desk">
        <div class="voice-desk-loading error-line">${esc(status.error)}</div>
        ${recoveryAction ? `<div class="voice-desk-actions">
          <button type="button" class="primary" data-live-action="${esc(recoveryAction.id)}">${esc(directorActionLabel(recoveryAction))}</button>
        </div>` : ""}
      </section>`;
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
    const take = status.takeUrl
      ? { url: status.takeUrl, label: "Current generated performance" }
      : (app.session?.artifact?.type === "audio" ? app.session.artifact : null);
    const auditions = status.auditions || {};
    const auditionCandidates = auditions.candidates || [];
    const selectedAudition = auditions.selected || {};
    return `<section class="voice-desk">
      <div class="voice-desk-head">
        <div><span class="stage-label">ELEVENLABS PERFORMANCE · ${esc(selectedShot?.shotId || app.shotId || "CURRENT SHOT")}${selectedShot?.durationSec ? ` · ${Number(selectedShot.durationSec)}s` : ""}</span><h3>Acting &amp; cadence prompt</h3></div>
        <span class="voice-source ${status.isWorking ? "working" : ""}">${esc(sourceLabel)}</span>
      </div>
      ${take?.url ? `<div class="voice-take-player">
        <div><span>Generated performance</span><strong>${esc(take.label || "Current take")}</strong>${status.takeGeneratedAt ? `<em>${esc(status.takeGeneratedAt)}</em>` : ""}</div>
        <audio controls preload="metadata" src="${esc(take.url)}?v=${Date.now()}"></audio>
      </div>` : ""}
      ${status.compiler?.error ? `<div class="voice-compiler-status blocked"><strong>Voice compiler blocked</strong><p>${esc(status.compiler.error)}</p></div>` : ""}
      ${status.compiler?.ready ? `<div class="voice-compiler-status ready"><strong>Post-Direction Audit passed</strong><p>The locked script, canon voice, performance questions, tag palette, context runway and take recipes are current.</p></div>` : ""}
      ${auditionCandidates.length ? `<section class="voice-auditions">
        <div class="voice-auditions-head"><div><span>HEAR DECISION</span><h4>${esc(auditions.character || "Voice")} · ${esc(auditions.archetypeId || "directed takes")}</h4></div><strong>${auditionCandidates.length} files ready</strong></div>
        <p>Listen and choose. Nothing is approved automatically. Your choice banks this character × archetype recipe${status.voiceApprovalRecorded ? ". The existing approved track stays protected until you reject it." : ", then builds the complete shot track for final HEAR approval."}</p>
        <div class="voice-audition-grid">${auditionCandidates.map((candidate) => {
          const chosen = selectedAudition.candidateId === candidate.candidateId;
          return `<article class="voice-audition ${chosen ? "selected" : ""}">
            <div><strong>${esc(candidate.label)}</strong><span>Take ${Number(candidate.takeNumber)}${candidate.primary ? " · Julian's primary direction" : ""}</span></div>
            <code>${esc(candidate.performedText)}</code>
            <audio controls preload="metadata" src="${esc(candidate.url || "")}"></audio>
            <button type="button" class="${chosen ? "secondary" : "primary"}" data-voice-audition="${esc(candidate.candidateId)}" ${chosen ? "disabled" : ""}>${chosen ? "Chosen" : (status.voiceApprovalRecorded ? "Choose take" : "Choose take & build track")}</button>
          </article>`;
        }).join("")}</div>
      </section>` : ""}
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
            <textarea id="voice-line-${index}" rows="3" data-voice-line="${index}" aria-label="${esc(line.speaker)} line ${index + 1} text and audio tags sent to ElevenLabs" ${status.compiler?.ready ? "readonly" : ""}>${esc(line.text)}</textarea>
          </article>`;
        }).join("") || '<div class="voice-desk-loading">This shot has no dialogue.</div>'}
      </div>
      ${lines.length ? `<div class="voice-desk-actions">
        ${status.compiler?.ready ? "" : `<button type="button" class="secondary" data-voice-restore ${status.isWorking ? "" : "disabled"}>Restore director prompt</button><button type="button" class="secondary" data-voice-save>Save changes</button>`}
        ${iterateAction ? `<button type="button" class="secondary danger" data-live-action="${esc(iterateAction.id)}">${esc(directorActionLabel(iterateAction))}</button>` : ""}
        ${acceptAction ? `<button type="button" class="secondary" data-live-action="${esc(acceptAction.id)}">${esc(directorActionLabel(acceptAction))}</button>` : ""}
        ${acceptAction ? `<button type="button" class="primary" data-live-action="${esc(acceptAction.id)}" data-advance-step="footage">${esc(directorActionLabel(acceptAction))} &amp; Continue</button>` : ""}
        ${sendAction ? `<button type="button" class="primary" data-voice-send="${esc(sendAction.id)}">${esc(directorActionLabel(sendAction))}</button>` : ""}
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

  async function selectVoiceAudition(candidateId) {
    if (!app.session?.selectedShotId) return;
    try {
      await api("/api/shot-voice-select-audition", {
        method: "POST",
        body: JSON.stringify({
          episode: app.session.episode,
          scene: app.session.scene,
          shotId: app.session.selectedShotId,
          candidateId,
        }),
      });
      await loadVoicePerformance(true);
      if (app.voiceStatus?.voiceApprovalRecorded) {
        toast("HEAR choice saved. The existing approved track remains protected; reject it before building its replacement.");
        return;
      }
      toast("HEAR choice saved. Building the complete shot track...");
      const actions = [app.session?.primaryAction, ...(app.session?.decisionActions || [])].filter(Boolean);
      const action = actions.find((item) => item.id === "build-voice");
      if (action) await handleAction(action);
    } catch (error) {
      toast(error.message, true);
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
    app.voiceStatus = null;
    app.voiceStatusKey = null;
    await submitAction(action);
    await loadVoicePerformance(true);
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

  function renderPipelineArtifact(step, session) {
    if (!["storyboard", "footage", "rough-cut"].includes(step.id)) return "";
    if (step.id === "footage" && session.status === "rendering") {
      return `<div class="pipeline-render-progress">${renderProgress(session)}</div>`;
    }
    const artifact = session.artifact || {};
    if (artifact.type === "video-set" && (artifact.items || []).length) {
      const items = artifact.items;
      return `<div class="pipeline-artifact">
        <video id="pipeline-candidate-video" controls playsinline preload="metadata" src="${esc(items[0].url)}?v=${Date.now()}"></video>
        <span>${esc(artifact.label || "Animation candidate")}</span>
        <div class="candidate-strip">${items.map((item, index) => `<button type="button" data-pipeline-candidate="${item.n}" data-url="${esc(item.url)}" class="${index === 0 ? "active" : ""}">C${item.n}</button>`).join("")}</div>
      </div>`;
    }
    if (artifact.type === "video" && artifact.url) {
      return `<div class="pipeline-artifact"><video controls playsinline preload="metadata" src="${esc(artifact.url)}?v=${Date.now()}"></video><span>${esc(artifact.label || "Current footage")}</span></div>`;
    }
    if (artifact.type === "image" && artifact.url) {
      return `<div class="pipeline-artifact"><img src="${esc(artifact.url)}?v=${Date.now()}" alt="${esc(artifact.label || "Current production result")}"><span>${esc(artifact.label || "Current result")}</span></div>`;
    }
    return "";
  }

  function renderCanonicalPipelineStep(step) {
    const details = {
      upload: ["Brief & script", "Import and lock the screenplay that governs every scene, line and story beat."],
      style: ["Visual style", "Lock the Crystal Bears 3D CGI profile, frame format and provider-safe visual language before paid downstream work."],
      analysis: ["Story & direction", "Turn the locked script into cinematic scenes and performance-led shots with humour, emotion and clear visual storytelling."],
      characters: ["Character assets", "Bind every character to approved turnarounds, structured identity traits, wardrobe, expressions and scene coverage."],
      props: ["Props & key objects", "Track canonical appearance, ownership, scene usage, allowed variations and approval for every story-critical object."],
      locations: ["Location clean plates", "Keep approved world plates, camera angles, light, weather and emotional state separate from story performance frames."],
      storyboard: ["Storyboard & keyframes", "Package direction into natural 4-30 second Seedance units: keep simple scenes long, split dense comedy/reveals, and approve the keyframe as visual truth."],
      footage: ["Footage", "Animate approved keyframes through the verified Seedance route, then review picture, lip sync, duration, drift and continuity separately. Split units end on held handoff frames."],
      audio: ["Audio performances", "Protect exact script lines while generating, repairing and approving character performances at line level."],
      "rough-cut": ["Rough cut & master", "Stitch accepted shots, expose missing media, then generate one ElevenLabs scene-level music cue and mix score, sound and colour for delivery."],
    }[step.id];
    const session = app.session || {};
    const liveStep = livePipelineStep(session);
    const index = pipelineSteps.findIndex((item) => item.id === step.id);
    const stepState = pipelineStepState(step, session);
    const selectedShot = (session.shots || []).find((shot) => shot.selected) || (session.shots || [])[0];
    const previous = pipelineSteps[index - 1];
    const next = pipelineSteps[index + 1];
    const availableActions = [session.primaryAction, ...(session.decisionActions || [])].filter(Boolean);
    const acceptAction = availableActions.find((action) => action.id.startsWith("accept-"));
    const iterateAction = availableActions.find((action) => action.id.startsWith("iterate-"));
    const otherActions = availableActions.filter((action) => action !== acceptAction && action !== iterateAction);
    const voiceDesk = step.id === "audio" ? renderVoicePerformanceDesk(availableActions) : "";
    const roughCutDesk = step.id === "rough-cut" ? renderRoughCutDesk() : "";
    const liveActionButtons = [
      acceptAction && `<button type="button" class="secondary" data-live-action="${esc(acceptAction.id)}">${esc(directorActionLabel(acceptAction))}</button>`,
      iterateAction && `<button type="button" class="secondary danger" data-live-action="${esc(iterateAction.id)}">${esc(directorActionLabel(iterateAction))}</button>`,
      acceptAction && next && `<button type="button" class="primary" data-live-action="${esc(acceptAction.id)}" data-advance-step="${esc(next.id)}">${esc(directorActionLabel(acceptAction))} &amp; Continue</button>`,
      ...otherActions.map((action, actionIndex) => `<button type="button" class="${actionIndex === 0 ? "primary" : "secondary"}${action.destructive ? " danger" : ""}" data-live-action="${esc(action.id)}">${esc(directorActionLabel(action))}</button>`),
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
      ${renderPipelineArtifact(step, session)}
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
    panel.querySelectorAll("[data-pipeline-scene]").forEach((button) => button.addEventListener("click", () => {
      if (button.dataset.pipelineScene === app.scene) return;
      app.scene = button.dataset.pipelineScene;
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
    const candidateButtons = panel.querySelectorAll("[data-pipeline-candidate]");
    if (candidateButtons.length) {
      app.selectedCandidate = Number(candidateButtons[0].dataset.pipelineCandidate);
      candidateButtons.forEach((button) => button.addEventListener("click", () => {
        app.selectedCandidate = Number(button.dataset.pipelineCandidate);
        candidateButtons.forEach((item) => item.classList.toggle("active", item === button));
        const video = $("#pipeline-candidate-video");
        video.src = `${button.dataset.url}?v=${Date.now()}`;
        video.play().catch(() => {});
      }));
    }
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
    panel.querySelectorAll("[data-voice-audition]").forEach((button) => button.addEventListener("click", () => selectVoiceAudition(button.dataset.voiceAudition)));
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
      const [roster, board] = await Promise.all([
        api(`/api/scene-roster?episode=${encodeURIComponent(app.episode)}`),
        api(`/api/director-board?episode=${encodeURIComponent(app.episode)}`),
      ]);
      app.roster = roster;
      app.directorBoard = board;
      renderEpisodes();
    } catch (error) {
      $("#scene-list").innerHTML = `<div class="reference-unavailable">${esc(error.message)}</div>`;
    }
  }

  async function refreshDirectorBoard() {
    try {
      app.directorBoard = await api(`/api/director-board?episode=${encodeURIComponent(app.episode)}`);
      renderEpisodes();
    } catch (_) {
      // The selected shot can still be used if the cross-scene projection is temporarily unavailable.
    }
  }

  function directorSessionSignature(session) {
    if (!session) return "";
    return JSON.stringify(session);
  }

  async function pollLiveSession() {
    clearTimeout(app.pollTimer);
    if (document.visibilityState !== "visible") {
      app.pollTimer = setTimeout(pollLiveSession, 15000);
      return;
    }
    const shot = app.shotId ? `&shotId=${encodeURIComponent(app.shotId)}` : "";
    try {
      const session = await api(`/api/director-session?episode=${encodeURIComponent(app.episode)}&scene=${encodeURIComponent(app.scene)}${shot}`, undefined, 60000);
      const changed = directorSessionSignature(session) !== directorSessionSignature(app.session);
      app.session = session;
      if (!app.shotId) app.shotId = session.selectedShotId || null;
      clearLocalActivityForSession(session);
      if (changed) {
        renderDirector(session);
        renderReview(session);
        if (app.view === "pipeline") renderPipeline();
      }
      app.pollTimer = setTimeout(pollLiveSession, session.status === "rendering" ? 1600 : 4500);
    } catch (_) {
      app.pollTimer = setTimeout(pollLiveSession, 4500);
    }
  }

  async function loadSession() {
    clearTimeout(app.pollTimer);
    const shot = app.shotId ? `&shotId=${encodeURIComponent(app.shotId)}` : "";
    try {
      if (!app.workbenchState || app.workbenchState.scene !== app.scene || app.workbenchState.episode !== app.episode) {
        await loadProjectWorkbenchState();
      }
      const session = await api(`/api/director-session?episode=${encodeURIComponent(app.episode)}&scene=${encodeURIComponent(app.scene)}${shot}`, undefined, 60000);
      app.session = session;
      if (!app.shotId) app.shotId = session.selectedShotId || null;
      if (session.phase === "keyframe") {
        await Promise.all([loadKeyframeLibrary(session), loadSceneAssetLibrary()]);
      }
      clearLocalActivityForSession(session);
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
      await refreshDirectorBoard();
      renderDirector(session);
      renderReview(session);
      renderStudioAgent();
      if (app.view === "pipeline") renderPipeline();
      loadStudioAgent();
      if (approvedAdvance) toast("Approved. Moving forward.");
      app.pollTimer = setTimeout(
        pollLiveSession, session.status === "rendering" ? 1600 : 4500);
    } catch (error) {
      const workbench = $("#scene-workbench");
      if (workbench) workbench.innerHTML = `<div class="relay-load-error"><strong>Studio state could not load</strong><p>${esc(error.message)}</p><button type="button" class="primary" data-retry-session>Retry</button></div>`;
      workbench?.querySelector("[data-retry-session]")?.addEventListener("click", loadSession);
      $("#media-stage").innerHTML = emptyStage(error.message, false);
      $("#outcome-headline").textContent = "Director state unavailable";
      $("#outcome-summary").textContent = error.message;
      $("#action-area").innerHTML = '<a class="secondary" href="/cb-studio/app.html">Open Inspector</a>';
      toast(error.message, true);
    }
  }

  async function waitForDirectorJob(jobId, { maxWaitMs = 60000 } = {}) {
    if (!jobId) return null;
    const started = Date.now();
    while (Date.now() - started < maxWaitMs) {
      const payload = await api("/api/jobs");
      const job = payload.jobs?.[jobId];
      if (job && !["running", "queued", "finalizing"].includes(job.status)) return job;
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
    return null;
  }

  function jobFailureMessage(job) {
    if (job?.error) return String(job.error);
    const lines = String(job?.log || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const important = [...lines].reverse().find((line) =>
      /REFUSED|ERROR|Error|Failed|failed|Bad Request|Client Error/i.test(line));
    return important || job?.step || "The job failed before returning a usable result.";
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

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Could not read uploaded keyframe."));
      reader.readAsDataURL(file);
    });
  }

  function setSourceSelectionActivity(label, message) {
    if (!app.session) return;
    const activity = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      actionId: "select-keyframe-source",
      shotId: app.session.selectedShotId,
      started: Date.now() / 1000,
      label,
      step: "Keyframe source",
      providerModelId: "zero-spend source selection",
    };
    setLocalActivity(activity);
    app.session = {
      ...app.session,
      status: "rendering",
      headline: label,
      summary: message,
      primaryAction: null,
      decisionActions: [],
      runningJob: {
        started: activity.started,
        activityLabel: label,
        step: activity.step,
        providerModelId: activity.providerModelId,
        latestMessage: message,
      },
    };
    renderDirector(app.session);
    if (app.view === "pipeline") renderPipeline();
  }

  async function runKeyframeSourceSelection(cmd, sourcePath, options = {}) {
    if (!app.session?.selectedShotId) return;
    if (!options.skipLockCheck && keyframeSourceLocked(app.session)) {
      toast("Review, approve or refire the current keyframe candidate before replacing it.", true);
      return;
    }
    if (!options.keepActivity) {
      setSourceSelectionActivity(
        cmd === "select-library" ? "Selecting library keyframe..." : "Selecting uploaded keyframe...",
        "Creating a reviewable keyframe candidate from the chosen source. No provider render spend."
      );
    }
    try {
      await api("/api/director-action", {
        method: "POST",
        body: JSON.stringify({
          action: cmd === "select-library" ? "select-keyframe-library" : "select-keyframe-upload",
          episode: app.session.episode,
          scene: app.session.scene,
          shotId: app.session.selectedShotId,
          sourcePath,
        }),
      });
      toast("Keyframe source submitted.");
      app.keyframeLibraryKey = null;
      setTimeout(loadSession, 350);
    } catch (error) {
      setLocalActivity(null);
      await loadSession();
      toast(error.message, true);
    }
  }

  async function selectKeyframeFromLibrary(sourcePath) {
    await runKeyframeSourceSelection("select-library", sourcePath);
  }

  async function uploadKeyframeSource(file) {
    if (!app.session?.selectedShotId) return;
    if (keyframeSourceLocked(app.session)) {
      toast("Review, approve or refire the current keyframe candidate before uploading a replacement.", true);
      return;
    }
    setSourceSelectionActivity("Uploading keyframe...", "Preserving the uploaded image before creating a review candidate. No provider render spend.");
    try {
      const dataB64 = await readFileAsDataUrl(file);
      const uploaded = await api("/api/shot-keyframe-upload", {
        method: "POST",
        body: JSON.stringify({
          episode: app.session.episode,
          scene: app.session.scene,
          shotId: app.session.selectedShotId,
          filename: file.name,
          dataB64,
        }),
      });
      await runKeyframeSourceSelection("select-upload", uploaded.sourcePath, { skipLockCheck: true, keepActivity: true });
    } catch (error) {
      setLocalActivity(null);
      await loadSession();
      toast(error.message, true);
    }
  }

  async function runScenePlateAction(actionId, sourcePath) {
    if (!app.session) return;
    setSourceSelectionActivity(
      actionId === "build-scene-plate" ? "Firing scene plate..." : "Selecting scene plate...",
      "Updating the scene plate source used by this scene. This does not approve the current keyframe."
    );
    try {
      const result = await api("/api/director-action", {
        method: "POST",
        body: JSON.stringify({
          action: actionId,
          episode: app.session.episode,
          scene: app.session.scene,
          shotId: app.session.selectedShotId,
          sourcePath,
        }),
      }, 60000);
      if (result.session) {
        setLocalActivity(null);
        app.session = result.session;
        renderDirector(app.session);
        if (app.view === "pipeline") renderPipeline();
        toast(actionId === "build-scene-plate" ? "Scene plate generation started." : "Scene plate updated.");
        return;
      }
      toast(actionId === "build-scene-plate" ? "Scene plate generation started." : "Scene plate source submitted.");
      await loadSession();
    } catch (error) {
      setLocalActivity(null);
      await loadSession();
      toast(error.message, true);
    }
  }

  async function uploadScenePlateSource(file) {
    if (!app.session) return;
    setSourceSelectionActivity("Uploading scene plate...", "Preserving the uploaded plate before assigning it to the scene.");
    try {
      const dataB64 = await readFileAsDataUrl(file);
      const uploaded = await api("/api/scenelook-upload", {
        method: "POST",
        body: JSON.stringify({
          episode: app.session.episode,
          scene: app.session.scene,
          filename: file.name,
          dataB64,
        }),
      });
      await runScenePlateAction("select-scene-plate-upload", uploaded.sourcePath);
    } catch (error) {
      setLocalActivity(null);
      await loadSession();
      toast(error.message, true);
    }
  }

  async function submitAction(action, note) {
    if (!app.session) return;
    const previousSession = app.session;
    $$("#action-area button").forEach((button) => { button.disabled = true; });
    const preparingRetry = action.id === "iterate-animation";
    const spend = previousSession.spendDisclosure || {};
    const copy = actionActivityCopy(action, previousSession, preparingRetry);
    const activity = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      actionId: action.id,
      shotId: previousSession.selectedShotId,
      started: Date.now() / 1000,
      label: copy.label,
      step: copy.step,
      durationSec: spend.shotDurationSec || previousSession.shot?.durationSec,
      candidateCount: spend.candidateCount,
      providerModelId: copy.provider || spend.providerModelId || previousSession.providerModel,
      resolution: spend.resolution,
      showDuration: !!copy.showDuration,
    };
    setLocalActivity(activity);
    app.session = {
      ...previousSession,
      status: "rendering",
      headline: activity.label,
      summary: copy.message,
      primaryAction: null,
      decisionActions: [],
      runningJob: {
        started: activity.started,
        activityLabel: copy.label,
        step: activity.step,
        durationSec: activity.durationSec,
        candidateCount: activity.candidateCount,
        maxBatchCostUsd: spend.maxBatchCostUsd,
        providerModelId: activity.providerModelId,
        latestMessage: copy.message,
      },
    };
    renderDirector(app.session);
    if (app.view === "pipeline") renderPipeline();
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
        setLocalActivity(null);
        location.href = result.navigate;
        return;
      }
      if (result.session) {
        setLocalActivity(null);
        app.session = result.session;
        renderDirector(app.session);
        if (app.view === "pipeline") renderPipeline();
        toast(result.noChange ? "Nothing changed." : "Scene plate updated.");
        return;
      }
      toast(result.noChange ? "Nothing changed." : "Director action started.");
      if (result.jobId) {
        const job = await waitForDirectorJob(result.jobId);
        if (!job) {
          await loadSession();
          toast("Still working. Live status remains on this shot.");
          return;
        }
        if (job && job.status === "failed") {
          const message = jobFailureMessage(job);
          holdLocalActivity(action, previousSession, message, "Action failed");
          await loadSession();
          toast(message, true);
          return;
        }
        setLocalActivity(null);
        await loadSession();
        if (action.id === "build-voice") await loadVoicePerformance(true);
        if (action.id === "accept-keyframe") {
          toast("Keyframe accepted. HEAR is now active.");
        }
        return;
      }
      setTimeout(loadSession, 350);
    } catch (error) {
      app.pendingAdvance = null;
      if (error.code === "DIRECTOR_ACTION_TIMEOUT") {
        toast(error.message);
        // Aborting the browser wait does not cancel a server-side decision already being
        // checked. Keep the honest in-progress card and let the normal live poll reconcile
        // the authoritative job/decision state instead of labelling it refused or inviting
        // a duplicate click.
        setTimeout(loadSession, 500);
        return;
      }
      holdLocalActivity(action, previousSession, error.message, "Action refused");
      if (error.payload?.session) {
        app.session = error.payload.session;
        renderDirector(app.session);
      } else {
        app.session = previousSession;
        renderDirector(app.session);
        if (app.view === "pipeline") renderPipeline();
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
      app.references = await api(`/api/shot-references?episode=${encodeURIComponent(app.session.episode)}&scene=${encodeURIComponent(app.session.scene)}&shotId=${encodeURIComponent(app.session.selectedShotId)}`, undefined, 60000);
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
      request.kind === "animation" && (request.providerModelId || app.session.providerModel)
        && `<span>${esc(request.providerModelId || app.session.providerModel)}</span>`,
      request.durationSec && `<span>${esc(Number(request.durationSec))}s</span>`,
      request.resolution && `<span>${esc(request.resolution)}</span>`,
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

  function updateKeyframePreviewZoom(nextZoom) {
    app.keyframeZoom = Math.min(3, Math.max(.5, nextZoom));
    const image = $("#keyframe-preview-image");
    const reset = $("#keyframe-zoom-reset");
    const out = $("#keyframe-zoom-out");
    const up = $("#keyframe-zoom-in");
    if (image) image.style.width = `${Math.round(app.keyframeZoom * 100)}%`;
    if (reset) reset.textContent = `${Math.round(app.keyframeZoom * 100)}%`;
    if (out) out.disabled = app.keyframeZoom <= .5;
    if (up) up.disabled = app.keyframeZoom >= 3;
  }

  function openKeyframePreview(url) {
    if (!url) return;
    const dialog = $("#keyframe-preview-dialog");
    const image = $("#keyframe-preview-image");
    if (!dialog || !image) return;
    image.src = url;
    updateKeyframePreviewZoom(1);
    dialog.showModal();
  }

  function bindEvents() {
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") loadSession();
    });
    $$('[data-view]').forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
    $$("[data-pipeline-step]").forEach((button) => button.addEventListener("click", () => {
      if (button.disabled) return;
      app.pipelineStep = button.dataset.pipelineStep;
      app.view = "pipeline";
      setView("pipeline");
    }));
    $("#continue-directing").addEventListener("click", openNextDecision);
    $("#references-button").addEventListener("click", openReferences);
    $("#request-button").addEventListener("click", openRequest);
    $("#request-close").addEventListener("click", closeRequest);
    $("#drawer-scrim").addEventListener("click", closeRequest);
    $("#keyframe-zoom-out").addEventListener("click", () => updateKeyframePreviewZoom(app.keyframeZoom - .25));
    $("#keyframe-zoom-reset").addEventListener("click", () => updateKeyframePreviewZoom(1));
    $("#keyframe-zoom-in").addEventListener("click", () => updateKeyframePreviewZoom(app.keyframeZoom + .25));
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
      const previousShot = app.shotId;
      const previousStep = app.pipelineStep;
      readHash();
      setView(app.view);
      if (app.scene !== previousScene || app.shotId !== previousShot) loadSession();
      if (app.view === "pipeline" && app.pipelineStep !== previousStep) renderPipeline();
    });
  }

  async function init() {
    readHash();
    bindEvents();
    await loadRoster();
    if (!app.explicitLocation && app.view === "director" && app.directorBoard?.nextDecision) {
      app.scene = String(app.directorBoard.nextDecision.scene);
      app.shotId = app.directorBoard.nextDecision.shotId || null;
      writeHash();
    }
    setView(app.view);
    renderPipeline();
    await loadSession();
    startBuildVersionWatch();
  }

  async function checkBuildVersion() {
    try {
      const current = await api("/api/studio-version");
      if (current.version === STUDIO_BUILD) return;
      document.body.classList.add("studio-stale");
      $("#stale-build-banner").hidden = false;
      clearInterval(app.buildTimer);
    } catch (_) {
      // Ordinary fetch recovery remains on the action that needs it.
    }
  }

  function startBuildVersionWatch() {
    $("#reload-studio").addEventListener("click", () => location.reload());
    checkBuildVersion();
    app.buildTimer = setInterval(checkBuildVersion, 10000);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
