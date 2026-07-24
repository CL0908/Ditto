import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Html, Float, useGLTF, useAnimations } from '@react-three/drei'
import { useSecurityStore } from '../state/store.js'
import { guardianIntroduce } from '../lib/useSecurityFeed.js'
import { LAYOUT } from '../lib/layout.js'
import titoUrl from '../../assets/tito.glb?url'

/**
 * Tito — AI guardian mascot of the smart home.
 *
 * Internal guardian states are mapped to Tito's visual states:
 *   idle      → normal   (purple glow, slow floating)
 *   detecting → warning  (orange glow, faster movement)
 *   alert     → critical (red glow, shaking)
 */
const STATE_MAP = { idle: 'normal', detecting: 'warning', alert: 'critical' }

const STATE_STYLE = {
  normal: { glow: new THREE.Color('#7C5CBF'), light: 14, floatSpeed: 1.6, floatIntensity: 0.6, spin: 0.5, sparkColor: '#7C5CBF' },
  warning: { glow: new THREE.Color('#ff9a3d'), light: 22, floatSpeed: 3.6, floatIntensity: 1.1, spin: 1.7, sparkColor: '#ffb066' },
  critical: { glow: new THREE.Color('#ff4444'), light: 28, floatSpeed: 2.2, floatIntensity: 0.7, spin: 0.9, sparkColor: '#ff6a55' },
}

/* wander behavior per state — Tito patrols the living room instead of hovering in place;
   on detection/alert he flies over to the attacked camera and hovers there scanning.
   Altitude is constant in every state: an angel-guardian hover above all furniture */
const WANDER = {
  normal:   { anchor: [0.7, 2.5, -1.2],  radius: 1.0,  yawFollow: true },  // free patrol around the room
  warning:  { anchor: [-1.5, 2.5, -3.1], radius: 0.45, yawFollow: false }, // closes in on the threat
  critical: { anchor: [-1.5, 2.5, -3.0], radius: 0.22, yawFollow: false }, // hovers right at the camera
}

/* ---- spatial constraints: stay inside the white floor grid, never clip furniture ---- */
const GRID_LIMIT = { x: 4.2, z: 3.7 }  // grid is ±5.1 / ±4.6, minus body margin
const Y_BAND = { min: 1.9, max: 2.6 }  // cruise band — above every furniture top, below the lamp
const BODY_R = 0.8                     // Tito's collision radius
/* furniture as axis-aligned boxes [minX, maxX, minY, maxY, minZ, maxZ] — measured from the scene */
const OBSTACLES = [
  [0.3, 3.3, 0, 1.3, 0.65, 2.0],      // sofa (scaled 1.25x)
  [1.05, 2.35, 0, 0.55, -0.62, 0.12], // coffee table (scaled 1.2x)
  [0.05, 0.95, 0, 0.5, -0.65, 0.25],  // pouf (scaled 1.2x)
  [-0.52, 0.02, 0, 0.8, 1.18, 1.72],  // air purifier (moved + scaled 1.15x)
  [-5.2, -3.4, 0, 1.85, -2.4, 0.0],   // desk + chair (scaled 1.15x)
  [-5.16, -4.7, 0, 2.5, -4.5, -2.2],  // bookshelf (scaled 1.15x)
  [0.2, 3.4, 0, 2.85, -4.7, -4.0],    // TV console + panel (scaled 1.2x)
  [-2.6, -0.6, 0, 3.9, -4.7, -4.35],  // window + security camera
  [3.3, 3.9, 0, 0.9, -4.7, -4.4],     // smart plug
  [-3.6, -1.2, 0, 1.0, 1.7, 4.1],     // dining set
  [3.45, 4.05, 0, 0.6, 1.1, 1.8],     // side table
  [4.35, 5.1, 0, 1.7, -4.45, -3.7],   // floor plant (back-right)
  [-5.1, -4.4, 0, 1.4, 3.9, 4.6],     // floor plant (front-left)
]

/* clamp a point into the grid and push it out of every furniture box (least-penetration axis) */
function confine(p) {
  p.x = THREE.MathUtils.clamp(p.x, -GRID_LIMIT.x, GRID_LIMIT.x)
  p.z = THREE.MathUtils.clamp(p.z, -GRID_LIMIT.z, GRID_LIMIT.z)
  p.y = THREE.MathUtils.clamp(p.y, Y_BAND.min, Y_BAND.max)
  for (const b of OBSTACLES) {
    const x0 = b[0] - BODY_R, x1 = b[1] + BODY_R
    const y0 = b[2] - BODY_R, y1 = b[3] + BODY_R
    const z0 = b[4] - BODY_R, z1 = b[5] + BODY_R
    if (p.x <= x0 || p.x >= x1 || p.y <= y0 || p.y >= y1 || p.z <= z0 || p.z >= z1) continue
    const dx = Math.min(p.x - x0, x1 - p.x)
    const dy = Math.min(p.y - y0, y1 - p.y)
    const dz = Math.min(p.z - z0, z1 - p.z)
    if (dx <= dy && dx <= dz) p.x = (p.x - x0 < x1 - p.x) ? x0 : x1
    else if (dy <= dz) p.y = (p.y - y0 < y1 - p.y) ? y0 : y1
    else p.z = (p.z - z0 < z1 - p.z) ? z0 : z1
  }
  return p
}

/* Expanding scan waves on the floor while Tito is analysing / alerting */
function ScanWaves({ active, color }) {
  const rings = useRef([])
  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    rings.current.forEach((m, i) => {
      if (!m) return
      const p = (t * 0.55 + i / 3) % 1
      m.scale.setScalar(0.3 + p * 4.2)
      m.material.opacity = active ? (1 - p) * 0.35 : 0
      m.material.color.set(color)
    })
  })
  return (
    <group>
      {[0, 1, 2].map((i) => (
        <mesh key={i} ref={(el) => (rings.current[i] = el)} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.94, 1, 48]} />
          <meshBasicMaterial color="#7C5CBF" transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} />
        </mesh>
      ))}
    </group>
  )
}

export default function TitoGuardian() {
  const guardian = useSecurityStore((s) => s.guardian)
  const select = useSecurityStore((s) => s.select)

  const { scene, animations } = useGLTF(titoUrl)
  const { actions } = useAnimations(animations, scene)

  const root = useRef()   // shake layer
  const spinner = useRef() // slow turntable rotation
  const glow = useRef()
  const aura = useRef()
  const mover = useRef()   // wander layer — the outer group, position driven per-frame
  const floorFx = useRef() // floor projection, glued under Tito while he wanders

  // wander state (mutated per-frame, no re-renders); starts parked at LAYOUT.guardian.pos
  const wv = useMemo(() => ({
    center: new THREE.Vector3(...LAYOUT.guardian.pos),
    pos: new THREE.Vector3(...LAYOUT.guardian.pos),
    prev: new THREE.Vector3(...LAYOUT.guardian.pos),
    vel: new THREE.Vector3(),
    radius: 0,
  }), [])

  const state = STATE_MAP[guardian.state] || 'normal'
  const style = STATE_STYLE[state]

  // Normalize the model: center it on the group origin and scale to ~1.5 units
  const { center, scale, materials } = useMemo(() => {
    const box = new THREE.Box3().setFromObject(scene)
    const size = box.getSize(new THREE.Vector3())
    const center = box.getCenter(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z) || 1
    const scale = 1.5 / maxDim

    const mats = new Set()
    scene.traverse((o) => {
      if (!o.isMesh) return
      o.frustumCulled = false
      const list = Array.isArray(o.material) ? o.material : [o.material]
      list.forEach((m) => {
        if (!m) return
        if (!('emissive' in m)) return
        if (!m.userData.baseEmissive) {
          m.userData.baseEmissive = m.emissive.clone()
          m.userData.baseEmissiveIntensity = m.emissiveIntensity ?? 1
        }
        mats.add(m)
      })
    })
    return { center, scale, materials: [...mats] }
  }, [scene])

  // Play the first embedded animation clip if the model ships one
  useEffect(() => {
    const first = Object.values(actions)[0]
    if (!first) return
    first.reset().fadeIn(0.3).play()
    return () => first.fadeOut(0.3)
  }, [actions])

  const tmp = useMemo(() => new THREE.Color(), [])

  useFrame(({ clock }, dt) => {
    const t = clock.elapsedTime

    // ---- wandering patrol ------------------------------------------------
    if (mover.current) {
      const w = WANDER[state]
      // patrol center glides toward the state's anchor (alert → flies to the camera)
      wv.center.x = THREE.MathUtils.damp(wv.center.x, w.anchor[0], 1.4, dt)
      wv.center.y = THREE.MathUtils.damp(wv.center.y, w.anchor[1], 1.4, dt)
      wv.center.z = THREE.MathUtils.damp(wv.center.z, w.anchor[2], 1.4, dt)
      wv.radius = THREE.MathUtils.damp(wv.radius, w.radius, 1.4, dt)
      // organic non-repeating path: incommensurate frequencies, never a plain circle
      const r = wv.radius
      const nx = wv.center.x + 2.4 * r * Math.sin(t * 0.11 + 1.3)
      const nz = wv.center.z + 1.7 * r * Math.sin(t * 0.073 + 4.1)
      // constant hover height — glides above every furniture piece like a guardian angel
      wv.prev.copy(wv.pos)
      wv.pos.set(nx, wv.center.y, nz)
      confine(wv.pos) // hard guarantee: inside the grid, outside the furniture
      mover.current.position.copy(wv.pos)
      // face the direction of travel while patrolling
      wv.vel.subVectors(wv.pos, wv.prev)
      if (w.yawFollow && wv.vel.lengthSq() > 1e-8) {
        const targetYaw = Math.atan2(wv.vel.x, wv.vel.z)
        const dy = targetYaw - mover.current.rotation.y
        mover.current.rotation.y += Math.atan2(Math.sin(dy), Math.cos(dy)) * (1 - Math.exp(-3 * dt))
      }
      // floor projection stays glued to the floor directly under Tito
      if (floorFx.current) floorFx.current.position.y = -wv.pos.y + 0.02
    }

    // critical = violent shake; otherwise settle back to center
    if (root.current) {
      if (state === 'critical') {
        root.current.position.x = Math.sin(t * 43) * 0.04
        root.current.position.z = Math.cos(t * 37) * 0.04
        root.current.rotation.z = Math.sin(t * 29) * 0.03
      } else {
        root.current.position.x = THREE.MathUtils.damp(root.current.position.x, 0, 8, dt)
        root.current.position.z = THREE.MathUtils.damp(root.current.position.z, 0, 8, dt)
        root.current.rotation.z = THREE.MathUtils.damp(root.current.rotation.z, 0, 8, dt)
      }
    }

    // turntable scan-spin only while anchored (warning/critical) — off while patrolling
    if (spinner.current && state !== 'normal') {
      spinner.current.rotation.y += dt * style.spin
    }

    // holographic tint on the model itself
    materials.forEach((m) => {
      tmp.copy(m.userData.baseEmissive).lerp(style.glow, state === 'normal' ? 0.18 : 0.38)
      m.emissive.lerp(tmp, 0.12)
    })

    if (glow.current) {
      const target = state === 'critical' ? style.light + Math.sin(t * 8) * 10 : style.light
      glow.current.intensity = THREE.MathUtils.lerp(glow.current.intensity, target, 0.1)
      glow.current.color.lerp(style.glow, 0.1)
    }

    if (aura.current) {
      aura.current.material.color.lerp(style.glow, 0.1)
      aura.current.material.opacity = state === 'critical'
        ? 0.07 + Math.abs(Math.sin(t * 6)) * 0.06
        : 0.05 + Math.sin(t * 1.6) * 0.02
      aura.current.scale.setScalar(1 + Math.sin(t * (state === 'critical' ? 6 : 1.6)) * 0.05)
    }
  })

  return (
    <group ref={mover} position={LAYOUT.guardian.pos}>
      <Float speed={style.floatSpeed} rotationIntensity={0.15} floatIntensity={style.floatIntensity} floatingRange={[-0.09, 0.09]}>
        <group ref={root}>
          {/* soft holographic aura */}
          <mesh ref={aura}>
            <sphereGeometry args={[0.95, 24, 24]} />
            <meshBasicMaterial color="#7C5CBF" transparent opacity={0.05} depthWrite={false} blending={THREE.AdditiveBlending} />
          </mesh>

          {/* Tito model — clickable, talks about privacy on click */}
          <group
            ref={spinner}
            onClick={(e) => { e.stopPropagation(); select('guardian'); guardianIntroduce() }}
            onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
            onPointerOut={() => { document.body.style.cursor = 'auto' }}
          >
            <group scale={scale}>
              <group position={[-center.x, -center.y, -center.z]}>
                <primitive object={scene} />
              </group>
            </group>
          </group>

          <pointLight ref={glow} color="#7C5CBF" intensity={14} distance={8} decay={2} />
        </group>
      </Float>

      {/* floor projection — follows Tito's wander, stays on the floor under him */}
      <group ref={floorFx}>
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.4, 0.44, 48]} />
          <meshBasicMaterial color={style.sparkColor} transparent opacity={0.4} depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} />
        </mesh>
        <mesh position={[0, -0.005, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[0.4, 40]} />
          <meshBasicMaterial color={style.sparkColor} transparent opacity={0.06} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>

        <ScanWaves active={guardian.state !== 'idle'} color={style.sparkColor} />
      </group>

      <Html position={[0, -1.05, 0]} center zIndexRange={[30, 0]}>
        <div className={`tag-chip ${guardian.state === 'alert' ? 'warn' : ''}`}>
          {guardian.state === 'alert' ? (
            <><span className="r">▲</span><span className="chip-name">Tito 守护者</span><span className="chip-status">· 发现威胁</span></>
          ) : guardian.state === 'detecting' ? (
            <>◌<span className="chip-name">Tito 守护者</span><span className="chip-status">· 扫描中…</span></>
          ) : (
            <><span className="g">●</span><span className="chip-name">Tito 守护者</span><span className="chip-status">· 在线</span></>
          )}
        </div>
      </Html>
    </group>
  )
}

useGLTF.preload(titoUrl)
