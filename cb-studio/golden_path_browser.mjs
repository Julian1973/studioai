#!/usr/bin/env node
/** Browser release gate for the Seven UX Laws.
 *
 * Runs the real Studio HTML/CSS/JS and authentication server. Only provider and
 * production API responses are mocked, so the test spends nothing while still
 * exercising the complete human journey and DOM event wiring.
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { mkdtemp, rm, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (error) {
  throw new Error("Playwright is required for the Studio Golden Path. Set NODE_PATH or install playwright.");
}

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
let activeStudio = null;
let activeBrowser = null;
let activeTemp = null;

async function freePort() {
  return await new Promise((resolve, reject) => {
    const server = createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function startStudio(port, secretFile) {
  const child = spawn("python3", ["-u", "cb-studio/serve.py"], {
    cwd: root,
    env: { ...process.env, CB_STUDIO_PORT: String(port),
      CB_STUDIO_SESSION_SECRET_FILE: secretFile,
      CB_STUDIO_STATE_DB: path.join(path.dirname(secretFile), "studio-test.sqlite3"),
      CB_STUDIO_SKIP_PREWARM: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  const launch = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error(`Studio did not start:\n${output}`));
    }, 60000);
    const consume = (chunk) => {
      output += chunk.toString();
      const match = output.match(/Animation Studio launch URL -> (\S+)/);
      if (match) { clearTimeout(timer); resolve(match[1]); }
    };
    child.stdout.on("data", consume);
    child.stderr.on("data", consume);
    child.once("error", (error) => { clearTimeout(timer); reject(error); });
    child.once("exit", (code) => { clearTimeout(timer); reject(new Error(`Studio exited ${code}:\n${output}`)); });
  });
  return { child, launch, output: () => output };
}

const onePixelPng = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
function oneSecondWav() {
  const sampleRate = 8000;
  const samples = Buffer.alloc(sampleRate, 128);
  const wav = Buffer.alloc(44 + samples.length);
  wav.write("RIFF", 0); wav.writeUInt32LE(36 + samples.length, 4); wav.write("WAVE", 8);
  wav.write("fmt ", 12); wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22); wav.writeUInt32LE(sampleRate, 24); wav.writeUInt32LE(sampleRate, 28);
  wav.writeUInt16LE(1, 32); wav.writeUInt16LE(8, 34); wav.write("data", 36);
  wav.writeUInt32LE(samples.length, 40); samples.copy(wav, 44);
  return `data:audio/wav;base64,${wav.toString("base64")}`;
}
const silentWav = oneSecondWav();
const emptyVideo = "data:video/mp4;base64,AAAAHGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDE=";

function action(id, label, { paid = false, destructive = false } = {}) {
  return { id, label, paid, destructive };
}

function sessionFor(step, notes, voiceUrl = silentWav, failure = null) {
  const common = {
    schemaVersion: 1,
    episode: "Ep1",
    scene: "1",
    sceneName: "Fuzzby's Pollination Lesson",
    selectedShotId: "S1.SH1A",
    shot: { shotId: "S1.SH1A", purpose: "Chase, false triumph and a clean comedy button.", durationSec: 9 },
    shots: [{ id: "S1.SH1A", shotId: "S1.SH1A", number: 1, selected: true, durationSec: 9,
      purpose: "Chase, false triumph and a clean comedy button.", keyframeUrl: onePixelPng,
      voiceUrl, acceptedUrl: emptyVideo, state: step === "complete" ? "complete" : "active" }],
    progress: { complete: step === "complete" ? 1 : 0, total: 1 },
    savedRetakeNotes: { ...notes },
    lineageCurrent: true,
    providerModel: "mock-seedance-2.5",
    providerReady: true,
    inspector: { structuralClaim: "Mocked Golden Path", providerRequest: { kind: "test", prompt: "Mock provider request" } },
    recentFailure: failure,
    stageComms: null,
  };
  if (step === "keyframe") return { ...common, phase: "keyframe", status: "ready_to_review",
    headline: "Does this opening frame work?", summary: "Review the visible stage.",
    artifact: { type: "image", url: onePixelPng, label: "Opening-frame candidate" },
    primaryAction: null, decisionActions: [action("accept-keyframe", "Accept"), action("iterate-keyframe", "Iterate", { destructive: true })] };
  if (step === "voice-ready") return { ...common, phase: "voice", status: "ready_to_fire",
    headline: "Opening frame accepted. Create the performances.", summary: "Create the dialogue performance.",
    artifact: { type: "image", url: onePixelPng }, primaryAction: action("build-voice", "Create performance", { paid: true }), decisionActions: [] };
  if (step === "voice-blocked") return { ...common, phase: "voice", status: "blocked",
    headline: "Voice setup needs attention", summary: "ElevenLabs rejected the configured credential.",
    artifact: { type: "image", url: onePixelPng }, primaryAction: action("build-voice", "Fix voice setup", { paid: true }), decisionActions: [],
    recentFailure: { jobId: "voice-refusal", error: "Voice build failed: ElevenLabs rejected the API credential." } };
  if (step === "voice-review") return { ...common, phase: "voice", status: "ready_to_review",
    headline: "Do the performances sound true?", summary: "Listen before deciding.",
    artifact: { type: "audio", url: voiceUrl, label: "Voice performance" }, primaryAction: null,
    decisionActions: [action("accept-voice", "Accept"), action("iterate-voice", "Iterate", { destructive: true })] };
  if (step === "animation-ready") return { ...common, phase: "animation", status: "ready_to_fire",
    headline: "Prepare the animation", summary: "Compile the approved frame and voice.",
    artifact: { type: "image", url: onePixelPng }, primaryAction: action("prepare-render", "Prepare render"), decisionActions: [] };
  if (step === "spend") return { ...common, phase: "animation", status: "ready_to_review",
    headline: "Request sealed", summary: "No video is rendering yet.", artifact: { type: "image", url: onePixelPng },
    spendDisclosure: { maxBatchCostUsd: 1.25, candidateCount: 1, shotDurationSec: 9, resolution: "480p", providerModelId: "mock-seedance-2.5" },
    primaryAction: null, decisionActions: [action("approve-spend", "Approve $1.25 & render", { paid: true }), action("cancel-spend", "Cancel")] };
  if (step === "animation-review") return { ...common, phase: "animation", status: "ready_to_review",
    headline: "Watch the result", summary: "Judge the rendered shot.", primaryAction: null,
    artifact: { type: "video-set", items: [{ n: 1, url: emptyVideo }] },
    decisionActions: [action("accept-animation", "Accept"), action("iterate-animation", "Iterate", { destructive: true })] };
  return { ...common, phase: "review", status: "complete", headline: "Shot accepted",
    summary: "Julian's verdict is recorded.", artifact: { type: "video", url: emptyVideo }, primaryAction: null, decisionActions: [] };
}

async function run() {
  const temp = await mkdtemp(path.join(tmpdir(), "cb-studio-golden-"));
  activeTemp = temp;
  const port = await freePort();
  const studio = await startStudio(port, path.join(temp, "session-secret"));
  activeStudio = studio;
  const base = `http://127.0.0.1:${port}`;
  const html = await readFile(path.join(root, "cb-studio", "director.html"), "utf8");
  const build = html.match(/<meta name="studio-build" content="([^"]+)"/)?.[1] || "unknown";
  const voiceUrl = `${base}/mock-voice.wav`;
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
    args: ["--autoplay-policy=no-user-gesture-required"],
  });
  activeBrowser = browser;
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  let step = "keyframe";
  let reportedBuild = build;
  let voiceAttempts = 0;
  let mediaAuditActive = false;
  let mediaSessionPolls = 0;
  const notes = {};
  const jobs = {};
  const requests = [];
  let mainNavigations = 0;
  page.on("framenavigated", (frame) => { if (frame === page.mainFrame()) mainNavigations += 1; });

  await context.route(voiceUrl, (route) => route.fulfill({
    status: 200,
    contentType: "audio/wav",
    body: Buffer.from(silentWav.split(",")[1], "base64"),
  }));

  await context.route(`${base}/api/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (pathname === "/api/studio-version") return json({ version: reportedBuild });
    if (pathname === "/api/scene-roster") return json({ scenes: Array.from({ length: 10 }, (_, i) => ({ sceneNumber: String(i + 1), location: `Scene ${i + 1}` })) });
    if (pathname === "/api/director-board") return json({ sceneCount: 10, nextDecision: { scene: "1", shotId: "S1.SH1A" }, scenes: [] });
    if (pathname === "/api/project-workbench-state") return json({ project: "crystal-bears", episode: "Ep1", scene: "1", retakeNotes: { ...notes } });
    if (pathname === "/api/shot-keyframe-library") return json({ items: [] });
    if (pathname === "/api/scene-asset-library") return json({ items: [] });
    if (pathname === "/api/studio-agent") return json({ summary: "Golden Path assistant ready." });
    if (pathname === "/api/shot-references") return json({ keyframe: { references: [] }, animation: { references: [] } });
    if (pathname === "/api/shot-voice-status") return json({ hasTake: step !== "voice-ready", takeUrl: voiceUrl, takeMatchesCurrent: true });
    if (pathname === "/api/rough-cut-draft") return json({ clips: [] });
    if (pathname === "/api/director-session") {
      if (mediaAuditActive) mediaSessionPolls += 1;
      return json(sessionFor(step, notes, voiceUrl));
    }
    if (pathname === "/api/jobs") {
      for (const job of Object.values(jobs)) {
        if (job.polls > 0) job.polls -= 1;
        else job.status = "done";
      }
      return json({ jobs });
    }
    if (pathname === "/api/director-action") {
      const body = request.postDataJSON();
      requests.push(body.action);
      if (body.action === "save-retake-note") {
        notes[`${body.shotId}:${body.stage}`] = body.note;
        return json({ ok: true, zeroSpend: true, savedNote: body.note });
      }
      if (body.action === "accept-keyframe") step = "voice-ready";
      else if (body.action === "build-voice") {
        voiceAttempts += 1;
        if (voiceAttempts === 1) {
          step = "voice-blocked";
          return json({ error: "Voice build failed: ElevenLabs rejected the API credential.", session: sessionFor(step, notes, voiceUrl) }, 409);
        }
        step = "voice-review";
      } else if (body.action === "accept-voice") step = "animation-ready";
      else if (body.action === "prepare-render") step = "spend";
      else if (body.action === "approve-spend") step = "animation-review";
      else if (body.action === "accept-animation") step = "complete";
      const jobId = `mock-${body.action}-${requests.length}`;
      jobs[jobId] = { jobId, status: "running", polls: 1, started: Date.now() / 1000, step: "Mock provider working", log: "Mock provider working" };
      return json({ ok: true, jobId });
    }
    return json({});
  });

  const target = `${studio.launch}#view=director&scene=1&shot=S1.SH1A&beat=chase`;
  await page.goto(target, { waitUntil: "domcontentloaded" });
  await page.getByText("Scene 1 of 10 · Shot 1 · Sign-off 1 of 3", { exact: true }).waitFor();
  const navigationBaseline = mainNavigations;
  await page.locator('[data-relay-note="1"]').fill("Keep the bee-height chase lane open.");
  await page.locator('[data-relay-note="1"]').blur();
  await page.getByText("Saved", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Accept", exact: true }).first().click();
  await page.getByText("Accepting keyframe", { exact: true }).first().waitFor();
  await page.getByText("Scene 1 of 10 · Shot 1 · Sign-off 2 of 3", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Create performance", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator("#toast").getByText("Voice build failed: ElevenLabs rejected the API credential.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Fix voice setup", exact: true }).first().waitFor();
  await page.getByRole("button", { name: "Fix voice setup", exact: true }).first().click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator(".relay-card.current .relay-audio-player audio").waitFor();
  await page.getByRole("button", { name: "Accept", exact: true }).first().click();
  await page.getByText("Scene 1 of 10 · Shot 1 · Sign-off 3 of 3", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Prepare render", exact: true }).click();
  await page.getByRole("button", { name: "Approve $1.25 & render", exact: true }).waitFor();
  await page.getByRole("button", { name: "Approve $1.25 & render", exact: true }).click();
  await page.getByRole("button", { name: "Render", exact: true }).click();
  await page.locator(".relay-card.current video").waitFor();
  await page.getByRole("button", { name: "Accept", exact: true }).first().click();
  await page.locator(".relay-card.complete").nth(2).waitFor();

  if (mainNavigations !== navigationBaseline) throw new Error("Golden Path reloaded the page instead of updating state in place.");
  if (notes["S1.SH1A:1"] !== "Keep the bee-height chase lane open.") throw new Error("Director note was not persisted.");
  const expected = ["accept-keyframe", "build-voice", "build-voice", "accept-voice", "prepare-render", "approve-spend", "accept-animation"];
  const productionActions = requests.filter((item) => item !== "save-retake-note");
  if (!requests.includes("save-retake-note") || JSON.stringify(productionActions) !== JSON.stringify(expected)) {
    throw new Error(`Unexpected action relay: ${JSON.stringify(requests)}`);
  }
  console.log("PASS Golden Path: launch -> SEE -> HEAR -> WATCH -> verdict");
  console.log("PASS Orientation remained explicit at every sign-off");
  console.log("PASS Provider refusal exposed its real cause and a Fix voice setup action");
  console.log("PASS Retake note persisted as a production diagnosis");
  console.log("PASS All state transitions completed without a page refresh");

  const canonicalHash = "#view=director&scene=1&shot=S1.SH1A&beat=chase";
  await page.evaluate((hash) => { location.hash = hash; }, canonicalHash);
  await page.waitForFunction((hash) => location.hash === hash, canonicalHash);
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByText("Scene 1 of 10 · Shot 1 · Sign-off 3 of 3", { exact: true }).waitFor();
  if ((await page.evaluate(() => location.hash)) !== canonicalHash) {
    throw new Error("Scene, shot and beat location changed after refresh.");
  }
  console.log("PASS Hash location survived refresh with identical scene, shot and beat");

  for (const label of ["Current Shot", "Scenes", "Pipeline"]) {
    await page.locator(".side-nav .nav-button", { hasText: label }).waitFor();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".mobile-nav").waitFor();
  for (const label of ["Shot", "Scenes", "Pipeline", "Master"]) {
    await page.locator(".mobile-nav button", { hasText: label }).waitFor();
  }
  console.log("PASS Navigation labels remained visible at desktop and mobile widths");

  await page.setViewportSize({ width: 1440, height: 1000 });
  step = "voice-review";
  mediaAuditActive = true;
  mediaSessionPolls = 0;
  const mediaPage = page;
  await mediaPage.addInitScript(() => {
    const nativeSetTimeout = window.setTimeout.bind(window);
    window.setTimeout = (callback, delay, ...args) => nativeSetTimeout(
      callback, delay === 4500 ? 250 : delay, ...args);
  });
  await mediaPage.goto(target, { waitUntil: "domcontentloaded" });
  const audio = mediaPage.locator(".relay-card.current audio");
  await audio.waitFor();
  const initialAudioState = await audio.evaluate((element) => new Promise((resolve) => {
    const ready = async () => {
      element.dataset.pollAudit = "same-node";
      try { await element.play(); } catch (_) {}
      setTimeout(() => {
        element.pause();
        resolve({ duration: element.duration, currentTime: element.currentTime });
      }, 600);
    };
    if (element.readyState >= 1) ready(); else element.addEventListener("loadedmetadata", ready, { once: true });
  }));
  if (initialAudioState.currentTime < 0.35) {
    throw new Error(`Golden audio fixture could not seek: ${JSON.stringify(initialAudioState)}`);
  }
  const imageSrc = await mediaPage.locator(".relay-card.complete img").first().getAttribute("src");
  const deadline = Date.now() + 5000;
  while (mediaSessionPolls < 11 && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  if (mediaSessionPolls < 11) throw new Error(`Only observed ${mediaSessionPolls} Director-session polls.`);
  const mediaState = await mediaPage.evaluate(() => ({
    audioTime: document.querySelector(".relay-card.current audio")?.currentTime || 0,
    audioMarker: document.querySelector(".relay-card.current audio")?.dataset.pollAudit || "",
    imageSrc: document.querySelector(".relay-card.complete img")?.getAttribute("src") || "",
    orientationCount: document.querySelectorAll(".relay-orientation").length,
    currentCards: document.querySelectorAll(".relay-card.current").length,
  }));
  if (mediaState.audioTime < 0.35 || mediaState.audioMarker !== "same-node" || mediaState.imageSrc !== imageSrc) {
    throw new Error(`Media state did not survive polling: ${JSON.stringify(mediaState)}`);
  }
  if (mediaState.orientationCount !== 1 || mediaState.currentCards !== 1) {
    throw new Error(`Progress model disagreed with itself: ${JSON.stringify(mediaState)}`);
  }
  console.log("PASS Image and audio position survived 10 live-state polls");
  console.log("PASS One orientation and one current sign-off remained authoritative");
  mediaAuditActive = false;

  const staleTab = await context.newPage();
  await staleTab.addInitScript(() => {
    const nativeSetInterval = window.setInterval.bind(window);
    window.setInterval = (callback, delay, ...args) => nativeSetInterval(
      callback, delay === 10000 ? 50 : delay, ...args);
  });
  await staleTab.goto(target, { waitUntil: "domcontentloaded" });
  await staleTab.getByText("Scene 1 of 10 · Shot 1 · Sign-off 2 of 3", { exact: true }).waitFor();
  reportedBuild = `${build}-next`;
  await staleTab.locator("#stale-build-banner").waitFor();
  const staleGuard = await staleTab.evaluate(() => ({
    stale: document.body.classList.contains("studio-stale"),
    workspacePointerEvents: getComputedStyle(document.querySelector(".workspace")).pointerEvents,
    sideNavPointerEvents: getComputedStyle(document.querySelector(".side-nav")).pointerEvents,
  }));
  if (!staleGuard.stale || staleGuard.workspacePointerEvents !== "none" || staleGuard.sideNavPointerEvents !== "none") {
    throw new Error(`Stale build did not block actions: ${JSON.stringify(staleGuard)}`);
  }
  console.log("PASS A stale second tab detected the new build and blocked production actions");
  reportedBuild = build;


  studio.child.kill("SIGTERM");
  await Promise.race([
    new Promise((resolve) => studio.child.once("exit", resolve)),
    new Promise((resolve) => setTimeout(resolve, 2000)),
  ]);
  await Promise.race([context.close(), new Promise((resolve) => setTimeout(resolve, 2000))]);
  await Promise.race([browser.close(), new Promise((resolve) => setTimeout(resolve, 2000))]);
  await rm(temp, { recursive: true, force: true });
  activeBrowser = null;
  activeStudio = null;
  activeTemp = null;
}

try {
  await run();
} catch (error) {
  try { await activeBrowser?.close(); } catch (_) {}
  try { activeStudio?.child.kill("SIGTERM"); } catch (_) {}
  try { if (activeTemp) await rm(activeTemp, { recursive: true, force: true }); } catch (_) {}
  console.error(`FAIL Golden Path: ${error.stack || error}`);
  process.exitCode = 1;
}
