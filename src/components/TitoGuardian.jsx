import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Html, Float, Sparkles, useGLTF, useAnimations } from '@react-three/drei'
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
  normal: { glow: new THREE.Color('#8b5cf6'), light: 14, floatSpeed: 1.6, floatIntensity: 0.6, spin: 0.5, sparkSpeed: 0.7, sparkColor: '#8b5cf6' },
  warning: { glow: new THREE.Color('#ff9a3d'), light: 22, floatSpeed: 3.6, floatIntensity: 1.1, spin: 1.7, sparkSpeed: 1.8, sparkColor: '#ffb066' },
  critical: { glow: new THREE.Color('#ff4444'), light: 28, floatSpeed: 2.2, floatIntensity: 0.7, spin: 0.9, sparkSpeed: 2.6, sparkColor: '#ff6a55' },
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
    <group position={[LAYOUT.guardian.pos[0], 0.02, LAYOUT.guardian.pos[2]]}>
      {[0, 1, 2].map((i) => (
        <mesh key={i} ref={(el) => (rings.current[i] = el)} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.94, 1, 48]} />
          <meshBasicMaterial color="#8b5cf6" transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} />
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

    if (spinner.current) {
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
    <group position={LAYOUT.guardian.pos}>
      <Float speed={style.floatSpeed} rotationIntensity={0.15} floatIntensity={style.floatIntensity} floatingRange={[-0.09, 0.09]}>
        <group ref={root}>
          {/* soft holographic aura */}
          <mesh ref={aura}>
            <sphereGeometry args={[0.95, 24, 24]} />
            <meshBasicMaterial color="#8b5cf6" transparent opacity={0.05} depthWrite={false} blending={THREE.AdditiveBlending} />
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

          <Sparkles
            count={state === 'normal' ? 55 : 90}
            scale={[2.2, 2.2, 2.2]}
            size={2.6}
            speed={style.sparkSpeed}
            color={style.sparkColor}
            opacity={0.8}
          />

          <pointLight ref={glow} color="#8b5cf6" intensity={14} distance={8} decay={2} />
        </group>
      </Float>

      {/* pedestal projection */}
      <mesh position={[0, -LAYOUT.guardian.pos[1] + 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.4, 0.44, 48]} />
        <meshBasicMaterial color={style.sparkColor} transparent opacity={0.4} depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, -LAYOUT.guardian.pos[1] + 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.4, 40]} />
        <meshBasicMaterial color={style.sparkColor} transparent opacity={0.06} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>

      <ScanWaves active={guardian.state !== 'idle'} color={style.sparkColor} />

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
