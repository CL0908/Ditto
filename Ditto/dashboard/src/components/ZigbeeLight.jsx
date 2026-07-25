import { useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import { useSecurityStore } from '../state/store.js'
import { LAYOUT } from '../lib/layout.js'

/**
 * Zigbee Smart Light — ceiling pendant.
 * normal  → warm steady light, green status dot
 * warning → violent flicker, red aura
 */
export default function ZigbeeLight() {
  const device = useSecurityStore((s) => s.devices.light_01)
  const select = useSecurityStore((s) => s.select)
  const lamp = useRef()
  const bulb = useRef()
  const dot = useRef()
  const aura = useRef()

  const warning = device.status === 'warning'

  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    let intensity = 26
    if (warning) {
      // flicker: random dropouts + buzz
      const drop = Math.sin(t * 13.7) * Math.sin(t * 7.3) * Math.sin(t * 29.1)
      intensity = drop > -0.15 ? 20 + Math.sin(t * 47) * 9 : 1.5
    }
    if (lamp.current) lamp.current.intensity = THREE.MathUtils.lerp(lamp.current.intensity, intensity, 0.5)
    if (bulb.current) {
      const m = bulb.current.material
      m.emissiveIntensity = THREE.MathUtils.lerp(m.emissiveIntensity, warning ? (intensity > 5 ? 2.4 : 0.1) : 2.2, 0.4)
      m.emissive.set(warning ? '#ff9a5c' : '#ffd9a0')
    }
    if (dot.current) {
      const m = dot.current.material
      m.color.set(warning ? '#ff4757' : '#34f5a5')
      m.emissive.set(warning ? '#ff2233' : '#1fd489')
      m.emissiveIntensity = warning ? (Math.sin(t * 8) > 0 ? 2.6 : 0.3) : 1.5
    }
    if (aura.current) {
      aura.current.visible = warning
      const s = 1 + Math.sin(t * 5) * 0.15
      aura.current.scale.setScalar(s)
      aura.current.material.opacity = 0.1 + Math.abs(Math.sin(t * 5)) * 0.12
    }
  })

  return (
    <group position={LAYOUT.light.pos}>
      {/* cord + shade */}
      <mesh position={[0, 0.44, 0]}>
        <cylinderGeometry args={[0.012, 0.012, 0.9, 6]} />
        <meshStandardMaterial color="#8d84a8" roughness={0.7} />
      </mesh>
      <mesh position={[0, -0.05, 0]}>
        <cylinderGeometry args={[0.07, 0.4, 0.34, 28, 1, true]} />
        <meshStandardMaterial color="#d9d2ea" roughness={0.5} metalness={0.2} side={THREE.DoubleSide} />
      </mesh>
      {/* generous invisible hit-area around the whole pendant */}
      <mesh
        visible={false}
        position={[0, -0.1, 0]}
        onClick={(e) => { e.stopPropagation(); select('light_01') }}
        onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { document.body.style.cursor = 'auto' }}
      >
        <sphereGeometry args={[0.6, 12, 12]} />
      </mesh>
      {/* bulb */}
      <mesh ref={bulb} position={[0, -0.16, 0]}>
        <sphereGeometry args={[0.11, 18, 18]} />
        <meshStandardMaterial color="#fff2dd" emissive="#ffd9a0" emissiveIntensity={2.2} roughness={0.3} />
      </mesh>
      {/* zigbee status dot */}
      <mesh ref={dot} position={[0.3, 0.08, 0.18]}>
        <sphereGeometry args={[0.018, 10, 10]} />
        <meshStandardMaterial color="#34f5a5" emissive="#1fd489" emissiveIntensity={1.5} />
      </mesh>
      {/* red warning aura */}
      <mesh ref={aura} visible={false}>
        <sphereGeometry args={[0.62, 20, 20]} />
        <meshBasicMaterial color="#ff4433" transparent opacity={0.12} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>

      <pointLight ref={lamp} position={[0, -0.35, 0]} color="#ffc27a" intensity={26} distance={13} decay={2} />

      <Html position={[0, -0.62, 0]} center zIndexRange={[30, 0]}>
        <div className={`tag-chip ${warning ? 'warn' : ''}`}>
          {warning ? (
            <><span className="r">▲</span><span className="chip-name">Zigbee 智能灯</span><span className="chip-status">· 行为：异常</span></>
          ) : (
            <><span className="g">●</span><span className="chip-name">Zigbee 智能灯</span><span className="chip-status">· 行为：正常</span></>
          )}
        </div>
      </Html>
    </group>
  )
}
