import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Html, Line, Sparkles } from '@react-three/drei'
import { useSecurityStore } from '../state/store.js'
import { LAYOUT } from '../lib/layout.js'

const v3 = (a) => new THREE.Vector3(a[0], a[1], a[2])

/* Particles flowing along a quadratic bezier; jitter makes traffic look corrupted */
function Flow({ from, to, lift = 1.2, color = '#4f9dff', count = 7, speed = 0.16, jitter = 0, size = 0.035 }) {
  const refs = useRef([])
  const curve = useMemo(() => {
    const a = v3(from)
    const b = v3(to)
    const mid = a.clone().lerp(b, 0.5)
    mid.y += lift
    return new THREE.QuadraticBezierCurve3(a, mid, b)
  }, [from, to, lift])

  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    for (let i = 0; i < count; i++) {
      const m = refs.current[i]
      if (!m) continue
      const p = (t * speed + i / count) % 1
      const pos = curve.getPoint(p)
      if (jitter > 0) {
        pos.x += Math.sin(p * 55 + t * 14) * jitter
        pos.y += Math.cos(p * 47 + t * 11) * jitter
        pos.z += Math.sin(p * 38 + t * 9) * jitter
      }
      m.position.copy(pos)
    }
  })

  return (
    <group>
      {Array.from({ length: count }).map((_, i) => (
        <mesh key={i} ref={(el) => (refs.current[i] = el)}>
          <sphereGeometry args={[size, 8, 8]} />
          <meshBasicMaterial color={color} />
        </mesh>
      ))}
    </group>
  )
}

function curvePoints(from, to, lift) {
  const a = v3(from)
  const b = v3(to)
  const mid = a.clone().lerp(b, 0.5)
  mid.y += lift
  return new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(40)
}

/* Holographic secure-cloud node hovering above the apartment */
function CloudNode() {
  const pulse = useRef()
  useFrame(({ clock }) => {
    if (pulse.current) {
      const s = 1 + Math.sin(clock.elapsedTime * 1.4) * 0.06
      pulse.current.scale.setScalar(s)
    }
  })
  return (
    <group position={LAYOUT.cloud.pos}>
      <group ref={pulse}>
        {[[-0.22, 0, 0], [0.05, 0.1, 0], [0.28, -0.02, 0]].map((p, i) => (
          <mesh key={i} position={p}>
            <sphereGeometry args={[0.22 - i * 0.03, 18, 18]} />
            <meshStandardMaterial color="#e6eeff" emissive="#5f9dff" emissiveIntensity={0.6} roughness={0.4} transparent opacity={0.95} />
          </mesh>
        ))}
        <mesh>
          <sphereGeometry args={[0.52, 20, 20]} />
          <meshBasicMaterial color="#7fb2ff" transparent opacity={0.12} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>
      </group>
      <Html position={[0, 0.62, 0]} center zIndexRange={[25, 0]}>
        <div className="net-chip blue">安全云 · TLS 1.3</div>
      </Html>
    </group>
  )
}

/* Hostile endpoint that materialises outside the home during the attack —
   soft pastel-styled "unknown sender" orb: warm-red core + radar ring + gentle glow */
function IntruderNode() {
  const core = useRef()
  const ring = useRef()
  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    if (core.current) {
      const s = 1 + Math.abs(Math.sin(t * 4)) * 0.12
      core.current.scale.setScalar(s)
    }
    if (ring.current) {
      ring.current.rotation.z = t * 1.2
      ring.current.rotation.x = Math.PI / 2.4 + Math.sin(t * 0.9) * 0.25
    }
  })
  return (
    <group position={LAYOUT.intruder.pos}>
      <mesh ref={core}>
        <sphereGeometry args={[0.22, 24, 24]} />
        <meshStandardMaterial color="#f7cdd3" emissive="#E85A6B" emissiveIntensity={1.1} roughness={0.35} />
      </mesh>
      <mesh ref={ring}>
        <torusGeometry args={[0.38, 0.018, 12, 40]} />
        <meshBasicMaterial color="#E85A6B" transparent opacity={0.65} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.46, 18, 18]} />
        <meshBasicMaterial color="#E85A6B" transparent opacity={0.1} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
      <Sparkles count={16} scale={[1.2, 1.2, 1.2]} size={2.5} speed={1.6} color="#E85A6B" opacity={0.7} />
      <Html position={[0, 0.72, 0]} center zIndexRange={[25, 0]}>
        <div className="net-chip">未知目标 · 185.220.▮.▮</div>
      </Html>
    </group>
  )
}

/**
 * NetworkGraph — the invisible cyber layer.
 * secure → clean blue streams to the cloud
 * attack → corrupted red path to an unknown external IP + warning labels
 */
export default function NetworkGraph() {
  const network = useSecurityStore((s) => s.network)
  const camStatus = useSecurityStore((s) => s.devices.camera_01.status)
  const attack = network.mode === 'attack'
  const camOff = camStatus === 'quarantined'

  const camTop = [LAYOUT.camera.pos[0], LAYOUT.camera.pos[1] + 0.25, LAYOUT.camera.pos[2] + 0.2]
  const cloud = LAYOUT.cloud.pos
  const intruder = LAYOUT.intruder.pos
  const lightTop = [LAYOUT.light.pos[0], LAYOUT.light.pos[1] + 0.2, LAYOUT.light.pos[2]]
  const plugTop = [LAYOUT.plug.pos[0], LAYOUT.plug.pos[1] + 0.1, LAYOUT.plug.pos[2]]

  const camCloud = useMemo(() => curvePoints(camTop, cloud, 1.1), [])
  const lightCloud = useMemo(() => curvePoints(lightTop, cloud, 0.9), [])
  const plugCloud = useMemo(() => curvePoints(plugTop, cloud, 1.4), [])
  const camIntruder = useMemo(() => curvePoints(camTop, intruder, 1.6), [])
  const midRed = useMemo(() => {
    const a = v3(camTop); const b = v3(intruder); const m = a.lerp(b, 0.5); m.y += 1.6
    return [m.x, m.y, m.z]
  }, [])

  return (
    <group>
      <CloudNode />

      {/* trusted uplinks */}
      {!camOff && (
        <>
          <Line points={camCloud} color="#4f9dff" transparent opacity={attack ? 0.1 : 0.45} lineWidth={1} />
          {!attack && <Flow from={camTop} to={cloud} lift={1.1} color="#6fb8ff" count={7} speed={0.16} />}
        </>
      )}
      <Line points={lightCloud} color="#4f9dff" transparent opacity={0.14} lineWidth={0.7} />
      <Line points={plugCloud} color="#4f9dff" transparent opacity={0.14} lineWidth={0.7} />
      <Flow from={lightTop} to={cloud} lift={0.9} color="#4f9dff" count={3} speed={0.1} size={0.025} />
      <Flow from={plugTop} to={cloud} lift={1.4} color="#4f9dff" count={3} speed={0.12} size={0.025} />

      {/* hostile path */}
      {attack && !camOff && (
        <>
          <IntruderNode />
          <Line points={camIntruder} color="#E85A6B" transparent opacity={0.8} lineWidth={1.6} />
          <Flow from={camTop} to={intruder} lift={1.6} color="#E85A6B" count={16} speed={0.55} jitter={0.16} size={0.045} />

          <Html position={midRed} center zIndexRange={[25, 0]}>
            <div className="net-chip">流量激增 +{network.spike}%</div>
          </Html>
          <Html position={[midRed[0] + 2.6, midRed[1] + 0.9, midRed[2]]} center zIndexRange={[25, 0]}>
            <div className="net-chip">新通信模式</div>
          </Html>
        </>
      )}
    </group>
  )
}
