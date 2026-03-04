#!/usr/bin/env node
import { readFileSync } from 'fs';
import { execFileSync } from 'child_process';

/*
 * Wire all orphaned items to their parent feature/track.
 * Mapping is manual — each orphan gets a parent and connection type.
 */

// Parent IDs
const BOOTSTRAP     = '3743457d-0fad-4d42-9361-e1a4670b1688';
const PIPELINE      = '404db70c-62ec-4a1f-85bb-bbb5563e3298';
const VISIBILITY    = '2c54bedf-313a-4e03-bd53-41ff84c39c45';
const DOGFOODING    = 'e3fdc74d-b640-4968-9ec4-8f9153ba6c7d';
const FOUNDATION    = '0bd89667-64d5-4a81-ac4c-d252225bb769';
const TERMINAL      = 'c1e35905-eb7b-4abf-8b2a-63ef37789060';
const VIEWS         = '1d0b7445-6253-4581-9505-b18c1c721978';
const THEME         = 'c0cd61ae-bb9c-4a9b-afca-bd8cf1dcef06';
const ONTOLOGY      = '44bd4826-b86d-4342-9041-883eb50f974c';
const VT_ENHANCE    = '97d4f5b4-e7c7-4c7c-9997-e01fe426c331';
const DRILLDOWN     = '9ad7174c-2d1d-456a-a60c-86b18ca92304';
const PERSISTENCE   = '2083f287-8a22-4f0e-9072-b5cd39dce0c3';
const DISCOVERY_SUP = '29ba34a4-be37-4e2e-ba6d-f30a5cda38f2';
const CONNECTORS    = '4675b520-3f21-4a48-b081-fcdb0c1ddfea';
const STANDALONE    = '730004ed-1372-420d-9011-657b0a334c4a';
const BREADCRUMBS   = '90c892e3-59d7-44ba-872f-0d62898a699e';
const FORGE_LOOP    = 'f66a5788-0d96-41f3-9660-e85ae0d821c5';
const AGENT_MON     = 'b81d24e2-9632-4e2a-967e-8aa0742740a7';

// [orphanId, parentId, connectionType]
const wiring = [
  // Core decisions → Foundation & Discovery
  ['5632a099-62f6-4f38-9d20-992a3072f369', FOUNDATION, 'supports'],
  ['b16f899e-8e21-4d52-8ce6-2aecada67084', FOUNDATION, 'supports'],
  ['9e90b79c-ce89-4fdf-a831-0be0c0677594', FOUNDATION, 'supports'],
  ['f4702d82-992b-4027-a463-5cce923f9301', FOUNDATION, 'supports'],
  ['b323d38c-0950-46ed-a64f-beefb9b66f72', FOUNDATION, 'supports'],
  ['a11b2fe3-2b40-450c-804b-7c78e07813ed', FOUNDATION, 'supports'],
  ['7853f84d-b121-4b6a-9849-5ae2e6576732', CONNECTORS, 'supports'],
  ['cadd6004-8750-409c-857e-703061fd3f95', BOOTSTRAP, 'supports'],

  // Ideas → various
  ['2662567c-deac-4eec-9084-19d9756c093d', VISIBILITY, 'supports'],
  ['bdbdd363-894d-48ad-be45-1680d1095c37', PIPELINE, 'supports'],
  ['d45f80f0-43d5-48a2-bc80-83231f205c0c', PIPELINE, 'supports'],
  ['83bdd6a9-c0aa-4c42-bc74-f65d2e320d0d', FOUNDATION, 'supports'],
  ['1e555432-ce1c-4279-820c-0ba4fad53b2b', FOUNDATION, 'supports'],
  ['orphan-persistence-model', PERSISTENCE, 'supports'],
  ['orphan-voice-input', DISCOVERY_SUP, 'supports'],
  ['orphan-mobile-view', STANDALONE, 'supports'],
  ['idea-testing-strategy', PIPELINE, 'supports'],
  ['e3091928-0b0d-4656-984b-8a2764eda72a', DRILLDOWN, 'supports'],

  // Questions → various
  ['37a333aa-1f0a-4f0d-8cab-c349f06a08cd', FOUNDATION, 'supports'],
  ['5a836beb-afd4-4d21-b36d-1fe7c8a21eb8', FOUNDATION, 'supports'],
  ['417e5c2c-992a-40e1-8ba1-3bc7e25564b0', VISIBILITY, 'supports'],
  ['c38aa3ae-febb-4370-81ca-b22163825d10', ONTOLOGY, 'supports'],
  ['question-release-strategy', STANDALONE, 'supports'],

  // Threads → various
  ['c3e13f70-2740-4558-997e-7f1dcb7a39c8', BOOTSTRAP, 'supports'],
  ['86878969-e6cf-4002-8f50-b90122acf9ab', ONTOLOGY, 'supports'],
  ['19f05faa-d50d-4697-87d2-c77b5d710a26', PIPELINE, 'supports'],
  ['d28e17d8-b9e7-4484-84ec-27f83568371d', FOUNDATION, 'supports'],
  ['thread-impl-bootstrap', BOOTSTRAP, 'supports'],

  // Artifacts → various
  ['09bcd9f9-316d-411b-9b66-22a2ddfa093e', VIEWS, 'supports'],
  ['f29ec601-25ec-47c7-b5bb-6226512af135', ONTOLOGY, 'supports'],
  ['8d3b67d7-122e-4231-a9ba-cb5ced9c92a7', BOOTSTRAP, 'supports'],

  // Decisions (visibility) → Agent Visibility
  ['dec-visibility-01', VISIBILITY, 'supports'],
  ['dec-visibility-02', VISIBILITY, 'supports'],
  ['dec-visibility-03', VISIBILITY, 'supports'],
  ['dec-visibility-04', VISIBILITY, 'supports'],

  // Specs → various
  ['bf0f895c-f42e-4cbe-8322-101a4b6b8dff', VIEWS, 'supports'],
  ['8d091d8f-10ba-41c1-8867-41032c4a60ef', VISIBILITY, 'supports'],
  ['4b8c6dd8-cfb3-4d60-92b6-d745d7a4d4ce', VT_ENHANCE, 'supports'],
  ['46481456-5233-4dc1-974e-17ff6c6c15d0', VT_ENHANCE, 'supports'],
  ['6d1282a3-a64e-45c5-9c8c-fd2f46b1adc9', DRILLDOWN, 'supports'],

  // Decisions (ontology/realignment) → Product Ontology
  ['14d18445-158a-4c36-a352-8dbc7544c62f', ONTOLOGY, 'supports'],
  ['c77d78ed-dfa3-4222-89e6-b3694335c6bf', ONTOLOGY, 'supports'],
  ['13cfc103-0eaa-4c06-be0a-998174f49349', ONTOLOGY, 'supports'],

  // Decisions (forge-loop) → Forge-Loop track
  ['695aa0ff-6b48-4ddc-b19e-3d470a269c4e', FORGE_LOOP, 'supports'],
  ['4bb32a05-f128-4822-976e-ccc96eb4c3ec', FORGE_LOOP, 'supports'],
];

let success = 0, fail = 0;
for (const [fromId, toId, type] of wiring) {
  try {
    execFileSync('node', ['scripts/vision-track.mjs', 'connect', fromId, toId, '--type', type], { stdio: 'pipe' });
    success++;
    process.stdout.write('.');
  } catch (e) {
    fail++;
    process.stdout.write('x');
    console.error(`\n  FAIL: ${fromId} -> ${toId}: ${e.stderr?.toString().trim()}`);
  }
}
console.log(`\n\nDone: ${success} wired, ${fail} failed`);
