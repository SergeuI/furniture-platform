import {
  ACESFilmicToneMapping,
  AmbientLight,
  BoxGeometry,
  CanvasTexture,
  CatmullRomCurve3,
  Color,
  CylinderGeometry,
  DirectionalLight,
  Group,
  LinearFilter,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PCFSoftShadowMap,
  PMREMGenerator,
  PerspectiveCamera,
  PlaneGeometry,
  RepeatWrapping,
  Scene,
  ShadowMaterial,
  SRGBColorSpace,
  TubeGeometry,
  Vector3,
  WebGLRenderer,
} from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export function supportsMountingNodeCatalogAutoPreview({ mountingVariantKey = '', fasteningType = '' } = {}) {
  return String(mountingVariantKey).trim() === 'face_to_edge'
    && String(fasteningType).trim().toLowerCase() === 'confirmat';
}

function makeSeededRandom(seed = 1) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function makeCatalogTexture({ base = '#caa675', kind = 'wood', seed = 1, verticalGrain = false } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = 384;
  canvas.height = 384;
  const ctx = canvas.getContext('2d');
  const random = makeSeededRandom(seed);

  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 384, 384);

  if (kind === 'wood') {
    if (verticalGrain) {
      ctx.save();
      ctx.translate(384, 0);
      ctx.rotate(Math.PI / 2);
    }
    for (let i = 0; i < 48; i += 1) {
      const y = random() * 384;
      const bend = (random() - 0.5) * 11;
      ctx.strokeStyle = `rgba(94,53,25,${0.08 + random() * 0.18})`;
      ctx.lineWidth = 1.2 + random() * 3.8;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.bezierCurveTo(110, y + bend, 260, y - bend * 0.6, 384, y + bend * 0.3);
      ctx.stroke();
    }
    for (let i = 0; i < 26; i += 1) {
      const y = random() * 384;
      const drift = (random() - 0.5) * 16;
      ctx.strokeStyle = random() < 0.55
        ? `rgba(86,51,29,${0.035 + random() * 0.06})`
        : `rgba(255,230,188,${0.045 + random() * 0.07})`;
      ctx.lineWidth = 5 + random() * 14;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.bezierCurveTo(110, y + drift, 260, y - drift, 384, y + drift * 0.5);
      ctx.stroke();
    }
    for (let y = random() * 7; y < 384; y += 8 + random() * 15) {
      const bend = (random() - 0.5) * 8;
      ctx.strokeStyle = `rgba(116,74,36,${0.10 + random() * 0.11})`;
      ctx.lineWidth = 1.2 + random() * 2.6;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.bezierCurveTo(130, y + bend, 255, y - bend, 384, y + bend * 0.4);
      ctx.stroke();
    }
    for (let i = 0; i < 115; i += 1) {
      const y = random() * 384;
      const wobble = Math.sin(y * 0.06) * 2 + (random() - 0.5) * 3;
      ctx.strokeStyle = `rgba(135,91,46,${0.025 + random() * 0.06})`;
      ctx.lineWidth = 0.45 + random() * 0.8;
      ctx.beginPath();
      ctx.moveTo(0, y + wobble);
      ctx.bezierCurveTo(105, y - wobble * 0.35, 250, y + wobble * 0.6, 384, y - wobble * 0.2);
      ctx.stroke();
    }
    if (verticalGrain) ctx.restore();
  } else {
    for (let i = 0; i < 900; i += 1) {
      const x = random() * 384;
      const y = random() * 384;
      const size = 9 + random() * 42;
      const tone = random();
      ctx.fillStyle = tone < 0.35
        ? `rgba(73,45,23,${0.25 + random() * 0.4})`
        : tone < 0.72
          ? `rgba(154,100,51,${0.28 + random() * 0.38})`
          : `rgba(253,230,181,${0.42 + random() * 0.4})`;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate((random() - 0.5) * Math.PI);
      const halfWidth = size * (0.08 + random() * 0.12);
      ctx.beginPath();
      ctx.moveTo(-size * 0.5, -halfWidth);
      ctx.lineTo(size * (0.15 + random() * 0.3), -halfWidth * (0.4 + random()));
      ctx.lineTo(size * 0.5, halfWidth * (0.1 + random() * 0.5));
      ctx.lineTo(-size * (0.05 + random() * 0.3), halfWidth);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
    for (let i = 0; i < 3600; i += 1) {
      const size = 1 + random() * 4;
      ctx.fillStyle = random() < 0.55 ? 'rgba(67,43,24,0.38)' : 'rgba(255,243,213,0.52)';
      ctx.fillRect(random() * 384, random() * 384, size * (1 + random()), size);
    }
  }

  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearFilter;
  texture.needsUpdate = true;
  return texture;
}

function makeSoftShadowTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createRadialGradient(128, 128, 12, 128, 128, 126);
  gradient.addColorStop(0, 'rgba(61,55,48,0.28)');
  gradient.addColorStop(0.45, 'rgba(61,55,48,0.14)');
  gradient.addColorStop(1, 'rgba(61,55,48,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 256, 256);
  return new CanvasTexture(canvas);
}

function makePanelMesh(kind, thickness, woodMaterial, coreMaterial) {
  const group = new Group();
  const cutZ = 0.0;
  const rearZ = -0.65;
  const keptDepth = cutZ - rearZ;
  const cutFaceMaterials = [woodMaterial, woodMaterial, woodMaterial, woodMaterial, coreMaterial, woodMaterial];
  // Both boards stop at the SAME z plane: the entire near half of the joint is absent.
  const mesh = new Mesh(
    kind === 'vertical'
      ? new BoxGeometry(thickness, 0.96, keptDepth)
      : new BoxGeometry(0.98, thickness, keptDepth),
    cutFaceMaterials,
  );
  mesh.position.z = (rearZ + cutZ) / 2;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);

  group.position.set(
    kind === 'vertical' ? -thickness / 2 : 0.98 / 2,
    kind === 'vertical' ? 0 : -thickness / 2,
    0,
  );
  return group;
}

function makeConfirmat({
  length = 0.50,
  headDiameter = 0.095,
  headLength = 0.08,
  hexSize = 0.04,
  neckLength = 0.035,
  threadMajor = 0.07,
  threadCore = 0.035,
  tipLength = 0.028,
} = {}) {
  const group = new Group();

  const headRadius = headDiameter * 0.5;
  const majorRadius = threadMajor * 0.5;
  const coreRadius = threadCore * 0.5;
  const neckRadius = 0.03;
  const hexRadius = hexSize / Math.sqrt(3);

  const zinc = new MeshStandardMaterial({
    color: new Color('#e3e8eb'),
    metalness: 0.88,
    roughness: 0.18,
    envMapIntensity: 1.7,
  });

  const dark = new MeshStandardMaterial({
    color: new Color('#434a51'),
    metalness: 0.18,
    roughness: 0.38,
  });
  const grooveMetal = new MeshStandardMaterial({
    color: new Color('#a8b3b9'),
    metalness: 0.78,
    roughness: 0.27,
    envMapIntensity: 1.3,
  });

  const headCapLength = 0.022;
  const headConeLength = Math.max(0.01, headLength - headCapLength);

  const headCap = new Mesh(
    new CylinderGeometry(headRadius, headRadius, headCapLength, 48),
    zinc,
  );
  headCap.rotation.z = -Math.PI / 2;
  headCap.position.x = headCapLength * 0.5;
  headCap.castShadow = true;
  group.add(headCap);

  const headCone = new Mesh(
    new CylinderGeometry(neckRadius * 1.03, headRadius, headConeLength, 48),
    zinc,
  );
  headCone.rotation.z = -Math.PI / 2;
  headCone.position.x = headCapLength + headConeLength * 0.5;
  headCone.castShadow = true;
  group.add(headCone);

  const recess = new Mesh(
    new CylinderGeometry(hexRadius, hexRadius, 0.004, 6),
    dark,
  );
  recess.rotation.z = -Math.PI / 2;
  recess.position.x = -0.002;
  group.add(recess);

  const neck = new Mesh(
    new CylinderGeometry(neckRadius, neckRadius, neckLength, 40),
    zinc,
  );
  neck.rotation.z = -Math.PI / 2;
  neck.position.x = headLength + neckLength * 0.5;
  neck.castShadow = true;
  group.add(neck);

  const bodyLength = length - headLength - neckLength - tipLength;

  const root = new Mesh(
    new CylinderGeometry(coreRadius, coreRadius * 0.95, bodyLength, 40),
    grooveMetal,
  );
  root.rotation.z = -Math.PI / 2;
  root.position.x = headLength + neckLength + bodyLength * 0.5;
  root.castShadow = true;
  group.add(root);

  const threadRadius = (majorRadius - coreRadius) * 0.69;
  const helixRadius = majorRadius - threadRadius;
  const turns = 9.5;
  const segments = 304;
  const points = [];
  for (let i = 0; i <= segments; i += 1) {
    const t = i / segments;
    const angle = t * Math.PI * 2 * turns;
    const x = headLength + neckLength + bodyLength * (0.03 + 0.94 * t);
    const taper = 1 - Math.max(0, t - 0.86) * 0.9;
    const r = helixRadius * taper;
    points.push(new Vector3(x, Math.cos(angle) * r, Math.sin(angle) * r));
  }

  const thread = new Mesh(
    new TubeGeometry(new CatmullRomCurve3(points), segments, threadRadius, 5, false),
    zinc,
  );
  thread.castShadow = true;
  group.add(thread);

  const tip = new Mesh(
    new CylinderGeometry(coreRadius * 0.46, coreRadius * 0.95, tipLength, 32),
    zinc,
  );
  tip.rotation.z = -Math.PI / 2;
  tip.position.x = length - tipLength * 0.5;
  tip.castShadow = true;
  group.add(tip);

  group.userData.disposeCatalogPreview = () => {
    group.traverse((object) => {
      object.geometry?.dispose?.();
      if (Array.isArray(object.material)) object.material.forEach((m) => m?.dispose?.());
      else object.material?.dispose?.();
    });
  };

  return group;
}

export async function renderMountingNodeCatalogAutoPreview({
  holes = [],
  mountingVariantKey = 'face_to_edge',
  fasteningType = 'confirmat',
  verticalThicknessMm = 18,
  horizontalThicknessMm = 18,
  width = 1200,
  height = 900,
} = {}) {
  if (!supportsMountingNodeCatalogAutoPreview({ mountingVariantKey, fasteningType })) {
    throw new Error('Catalog auto preview is not supported for this mounting node.');
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;

  const renderer = new WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    preserveDrawingBuffer: true,
  });

  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = PCFSoftShadowMap;

  const scene = new Scene();
  scene.background = new Color('#ffffff');
  const roomEnvironment = new RoomEnvironment();
  const pmremGenerator = new PMREMGenerator(renderer);
  const environmentTarget = pmremGenerator.fromScene(roomEnvironment, 0.04);
  scene.environment = environmentTarget.texture;
  scene.environmentIntensity = 0.8;

  const camera = new PerspectiveCamera(22.5, width / height, 0.1, 100);
  camera.position.set(-1.4, 1.04, 2.12);
  camera.lookAt(new Vector3(0.10, 0.05, -0.03));

  scene.add(new AmbientLight('#ffffff', 0.38));

  const key = new DirectionalLight('#fffaf2', 1.45);
  key.position.set(-2.5, 3.7, 3.6);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -1.6;
  key.shadow.camera.right = 1.6;
  key.shadow.camera.top = 1.6;
  key.shadow.camera.bottom = -1.6;
  key.shadow.camera.near = 0.5;
  key.shadow.camera.far = 9;
  key.shadow.bias = -0.00015;
  key.shadow.normalBias = 0.012;
  key.shadow.radius = 3;
  scene.add(key);

  const fill = new DirectionalLight('#f6f9ff', 0.4);
  fill.position.set(2.6, 1.7, 2.2);
  scene.add(fill);

  const verticalWoodTexture = makeCatalogTexture({ base: '#c5a073', kind: 'wood', seed: 11, verticalGrain: true });
  const horizontalWoodTexture = makeCatalogTexture({ base: '#c5a073', kind: 'wood', seed: 17 });
  const verticalCoreTexture = makeCatalogTexture({ base: '#c7aa7e', kind: 'chipboard', seed: 29 });
  const horizontalCoreTexture = makeCatalogTexture({ base: '#c7aa7e', kind: 'chipboard', seed: 31 });
  verticalCoreTexture.wrapS = RepeatWrapping;
  verticalCoreTexture.wrapT = RepeatWrapping;
  verticalCoreTexture.repeat.set(1, 3);
  horizontalCoreTexture.wrapS = RepeatWrapping;
  horizontalCoreTexture.wrapT = RepeatWrapping;
  horizontalCoreTexture.repeat.set(3, 1);

  const verticalWoodMaterial = new MeshStandardMaterial({
    color: new Color('#d4b899'),
    map: verticalWoodTexture,
    metalness: 0.02,
    roughness: 0.48,
    bumpMap: verticalWoodTexture,
    bumpScale: 0.002,
    envMapIntensity: 0.65,
  });
  const horizontalWoodMaterial = new MeshStandardMaterial({
    color: new Color('#d4b899'),
    map: horizontalWoodTexture,
    metalness: 0.02,
    roughness: 0.48,
    bumpMap: horizontalWoodTexture,
    bumpScale: 0.002,
    envMapIntensity: 0.65,
  });

  const makeCoreMaterial = (texture) => new MeshStandardMaterial({
    color: new Color('#c3a47d'),
    map: texture,
    metalness: 0,
    roughness: 0.88,
    bumpMap: texture,
    bumpScale: 0.016,
    envMapIntensity: 0.55,
  });
  const verticalCoreMaterial = makeCoreMaterial(verticalCoreTexture);
  const horizontalCoreMaterial = makeCoreMaterial(horizontalCoreTexture);

  const verticalThickness = Math.max(0.14, Math.min(0.24, Number(verticalThicknessMm) * 0.01 || 0.18));
  const horizontalThickness = Math.max(0.14, Math.min(0.24, Number(horizontalThicknessMm) * 0.01 || 0.18));
  const panelMeshes = [
    makePanelMesh('vertical', verticalThickness, verticalWoodMaterial, verticalCoreMaterial),
    makePanelMesh('horizontal', horizontalThickness, horizontalWoodMaterial, horizontalCoreMaterial),
  ];
  panelMeshes.forEach((mesh) => scene.add(mesh));

  const screw = makeConfirmat({ length: 0.50, headDiameter: 0.095, headLength: 0.08, hexSize: 0.04, neckLength: 0.035, threadMajor: 0.07, threadCore: 0.035, tipLength: 0.028 });
  // The cut plane runs through the screw axis; its rear half remains inside both boards.
  screw.position.set(-verticalThickness - 0.025, -horizontalThickness / 2, 0);
  scene.add(screw);

  const floor = new Mesh(
    new PlaneGeometry(3.4, 3.4),
    new MeshBasicMaterial({ color: '#ffffff', toneMapped: false }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.505;
  scene.add(floor);

  const floorShadow = new Mesh(
    new PlaneGeometry(3.4, 3.4),
    new ShadowMaterial({ color: '#554c43', opacity: 0.32, depthWrite: false }),
  );
  floorShadow.rotation.x = -Math.PI / 2;
  floorShadow.position.y = -0.501;
  floorShadow.receiveShadow = true;
  scene.add(floorShadow);

  const softShadowTexture = makeSoftShadowTexture();
  const softShadow = new Mesh(
    new PlaneGeometry(1.75, 1.25),
    new MeshBasicMaterial({ map: softShadowTexture, transparent: true, depthWrite: false }),
  );
  softShadow.rotation.x = -Math.PI / 2;
  softShadow.position.set(0.25, -0.503, -0.18);
  scene.add(softShadow);

  try {
    renderer.render(scene, camera);
    return await new Promise((resolve, reject) => {
      canvas.toBlob((value) => {
        if (value) resolve(value);
        else reject(new Error('Catalog auto preview capture failed.'));
      }, 'image/png');
    });
  } finally {
    screw.userData.disposeCatalogPreview?.();
    panelMeshes.forEach((group) => group.traverse((object) => object.geometry?.dispose?.()));
    floor.geometry?.dispose?.();
    floor.material?.dispose?.();
    floorShadow.geometry?.dispose?.();
    floorShadow.material?.dispose?.();
    softShadow.geometry?.dispose?.();
    softShadow.material?.dispose?.();
    softShadowTexture.dispose();
    verticalWoodMaterial.dispose();
    horizontalWoodMaterial.dispose();
    verticalCoreMaterial.dispose();
    horizontalCoreMaterial.dispose();
    verticalWoodTexture.dispose();
    horizontalWoodTexture.dispose();
    verticalCoreTexture.dispose();
    horizontalCoreTexture.dispose();
    environmentTarget.dispose();
    pmremGenerator.dispose();
    roomEnvironment.dispose();
    renderer.dispose();
  }
}
