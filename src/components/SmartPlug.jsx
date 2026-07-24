import { useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html, RoundedBox, Line } from '@react-three/drei'
import { useSecurityStore } from '../state/store.js'
import { LAYOUT } from '../lib/layout.js'
import { deviceHealth } from '../state/store.js'

/** Energy pulses travelling from the plug up into the TV console */
function EnergyPulses({ from, to, count = 3 }) {
  const refs = useRef([])
  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    for (let i = 0; i < count; i++) {
      const m = refs.current[i]
      if (!m) continue
      const p = (t * 0.55 + i / count) % 1
      m.position.set(
        from[0] + (to[0] - from[0]) * p,
        from[1] + (to[1] - from[1]) * p,
        from[2] + (to[2] - from[2]) * p,
      )
      const s = 0.7 + Math.sin(p * Math.PI) * 0.6
      m.scale.setScalar(s)
    }
  })
  return (
    <group>
      {Array.from({ length: count }).map((_, i) => (
        <mesh key={i} ref={(el) => (refs.current[i] = el)}>
          <sphereGeometry args={[0.022, 8, 8]} />
          <meshBasicMaterial color="#8b5cf6" />
        </mesh>
      ))}
    </group>
  )
}

/**
 * Smart Plug — wall socket near the TV.
 * Always shows a live energy/data flow; ring LED breathes with load.
 */
export default function SmartPlug() {
  const device = useSecurityStore((s) => s.devices.plug_01)
  const select = useSecurityStore((s) => s.select)
  const ring = useRef()
  const [hovered, setHovered] = useState(false)

  const health = deviceHealth(device)
  const [x, y, z] = LAYOUT.plug.pos
  const cableStart = useMemo(() => [x + 0.02, y + 0.02, z + 0.06], [x, y, z])
  const cableEnd = useMemo(() => [2.15, 0.34, -4.18], [])
  const cableMid = useMemo(
    () => [(cableStart[0] + cableEnd[0]) / 2 + 0.1, 0.14, (cableStart[2] + cableEnd[2]) / 2 + 0.12],
    [cableStart, cableEnd],
  )

  useFrame(({ clock }) => {
    if (ring.current) {
      ring.current.material.emissiveIntensity = 1.1 + Math.sin(clock.elapsedTime * 2.4) * 0.5
    }
  })

  return (
    <group>
      {/* wall plate */}
      <mesh position={[x, y, z - 0.012]}>
        <boxGeometry args={[0.17, 0.17, 0.02]} />
        <meshStandardMaterial color="#f4f1fa" roughness={0.5} />
      </mesh>
      {/* plug body */}
      <RoundedBox args={[0.12, 0.1, 0.09]} radius={0.02} position={[x, y, z + 0.05]}>
        <meshStandardMaterial
          color="#f6f3fc"
          roughness={0.45}
          metalness={0.1}
          emissive={hovered ? '#9d8cf5' : '#000000'}
          emissiveIntensity={hovered ? 0.35 : 0}
        />
      </RoundedBox>
      {/* generous invisible hit-area */}
      <mesh
        visible={false}
        position={[x, y, z + 0.05]}
        onClick={(e) => { e.stopPropagation(); select('plug_01') }}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = 'auto' }}
      >
        <boxGeometry args={[0.55, 0.55, 0.5]} />
      </mesh>
      {/* LED ring */}
      <mesh ref={ring} position={[x, y, z + 0.098]}>
        <torusGeometry args={[0.032, 0.007, 10, 26]} />
        <meshStandardMaterial color="#e8e2f6" emissive="#8b5cf6" emissiveIntensity={1.4} roughness={0.3} />
      </mesh>

      {/* power cable into TV console + flow */}
      <Line points={[cableStart, cableMid, cableEnd]} color="#b3aad2" lineWidth={2.5} />
      <EnergyPulses from={cableStart} to={cableEnd} />

      <Html position={[x + 0.12, y + 0.34, z]} center zIndexRange={[30, 0]}>
        <div className="tag-chip">
          <span className="g">●</span><span className="chip-name">电源插座</span><span className="chip-status">· 健康度 {health}%</span>
        </div>
      </Html>
    </group>
  )
}
