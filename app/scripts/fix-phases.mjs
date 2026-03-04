#!/usr/bin/env node
import { execFileSync } from 'child_process';

// Reclassify all ideas, questions, and threads to vision phase
const reclassify = [
  // Ideas
  '2662567c-deac-4eec-9084-19d9756c093d',  // Dynamic decision chips
  'bdbdd363-894d-48ad-be45-1680d1095c37',  // Specialized agents per phase
  'd45f80f0-43d5-48a2-bc80-83231f205c0c',  // Background sub-agent for proactive AI
  '83bdd6a9-c0aa-4c42-bc74-f65d2e320d0d',  // General backbone + domain constraints
  '26779dbe-6a5b-4dbb-ac30-aacc97f044bf',  // Base44 insight: iteration is the value
  '1e555432-ce1c-4279-820c-0ba4fad53b2b',  // Knobs as control surface
  'orphan-persistence-model',                // Event-sourced persistence model
  'orphan-voice-input',                      // Voice input for rapid capture
  'orphan-mobile-view',                      // Mobile companion view
  'idea-testing-strategy',                   // Verification phase: AI tests its own output
  'e3091928-0b0d-4656-984b-8a2764eda72a',  // Drill-down views for Vision Tracker

  // Questions
  '37a333aa-1f0a-4f0d-8cab-c349f06a08cd',  // How do jigsaw pieces interface?
  '5a836beb-afd4-4d21-b36d-1fe7c8a21eb8',  // How to prove the thesis?
  '417e5c2c-992a-40e1-8ba1-3bc7e25564b0',  // What triggers decision chips?
  'c38aa3ae-febb-4370-81ca-b22163825d10',  // How does the item map scale?
  'question-release-strategy',               // What's the release packaging?

  // Threads
  'c3e13f70-2740-4558-997e-7f1dcb7a39c8',  // Design the first permanent piece
  '86878969-e6cf-4002-8f50-b90122acf9ab',  // Fill remaining matrix rows
  '19f05faa-d50d-4697-87d2-c77b5d710a26',  // Pipeline requirements
  'd28e17d8-b9e7-4484-84ec-27f83568371d',  // Knobs design
  'thread-impl-bootstrap',                   // Implementation bootstrap sequence

  // Vision decision
  '5632a099-62f6-4f38-9d20-992a3072f369',  // Vision: Build me X, Forge takes it from there
];

let success = 0, fail = 0;
for (const id of reclassify) {
  try {
    execFileSync('node', ['scripts/vision-track.mjs', 'update', id, '--phase', 'vision'], { stdio: 'pipe' });
    success++;
    process.stdout.write('.');
  } catch (e) {
    fail++;
    process.stdout.write('x');
    console.error(`\n  FAIL: ${id}: ${e.stderr?.toString().trim()}`);
  }
}
console.log(`\n\nDone: ${success} reclassified to vision, ${fail} failed`);
