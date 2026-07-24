import { useRef, useState } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Html, RoundedBox, Sparkles } from '@react-three/drei'
import { useSecurityStore } from '../state/store.js'
import { LAYOUT } from '../lib/layout.js'

/**
 * Smart Security Camera — wall-mounted CCTV.
 * normal      → slow patrol sweep, cyan scan cone, green LED, smooth data flow
 * warning     → jittery movement, red glow, unstable particles, risk tag
 * quarantined → powered down, drooped head, grey tag
 */
export default function CameraDevice() {
  const device = useSecurityStore((s) => s.devices.camera_01)
  const select = useSecurityStore((s) => s.select)
  const selected = useSecurityStore((s) => s.selected === 'camera_01')
  const [hovered, setHovered] = useState(false)

  const head = useRef()
  const led = useRef()
  const lens = useRef()
  const cone = useRef()
  const glow = useRef()

  const { status, risk } = device
  const warning = status === 'warning'
  const dead = status === 'quarantined'

  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    if (head.current) {
      if (dead) {
        head.current.rotation.y = THREE.MathUtils.lerp(head.current.rotation.y, 0, 0.05)
        head.current.rotation.x = THREE.MathUtils.lerp(head.current.rotation.x, 0.5, 0.05)
      } else if (warning) {
        // unstable: fast sweep + nervous jitter
        head.current.rotation.y = Math.sin(t * 1.6) * 0.55 + Math.sin(t * 23) * 0.03
        head.current.rotation.x = 0.12 + Math.sin(t * 31) * 0.02
      } else {
        head.current.rotation.y = Math.sin(t * 0.45) * 0.55
        head.current.rotation.x = 0.12
      }
    }
    if (led.current) {
      const m = led.current.material
      if (dead) {
        m.color.set('#3a4150'); m.emissive.set('#000000'); m.emissiveIntensity = 0
      } else if (warning) {
        const on = Math.sin(t * 9) > -0.2
        m.color.set(on ? '#ff4757' : '#5a121a')
        m.emissive.set('#ff2233')
        m.emissiveIntensity = on ? 3 : 0.2
      } else {
        m.color.set('#34f5a5'); m.emissive.set('#1fd489'); m.emissiveIntensity = 1.6
      }
    }
    if (lens.current) {
      const m = lens.current.material
      if (dead) { m.emissive.set('#000'); m.emissiveIntensity = 0 }
      else if (warning) { m.emissive.set('#ff3344'); m.emissiveIntensity = 1.4 + Math.sin(t * 9) * 1 }
      else { m.emissive.set('#5fa8ff'); m.emissiveIntensity = 0.9 }
    }
    if (cone.current) {
      cone.current.visible = !dead
      cone.current.material.opacity = warning ? 0.05 + Math.abs(Math.sin(t * 7)) * 0.05 : 0.045
      cone.current.material.color.set(warning ? '#ff5566' : '#7fb0ff')
    }
    if (glow.current) {
      const target = dead ? 0 : warning ? 6 + Math.abs(Math.sin(t * 8)) * 8 : 1.6
      glow.current.intensity = THREE.MathUtils.lerp(glow.current.intensity, target, 0.15)
      glow.current.color.set(warning ? '#ff4455' : '#8fb0ff')
    }
  })

  return (
    <group position={LAYOUT.camera.pos} rotation={[0, LAYOUT.camera.rotY, 0]}>
      {/* wall mount */}
      <mesh position={[0, 0.1, -0.16]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.045, 0.045, 0.24, 10]} />
        <meshStandardMaterial color="#a8afc4" roughness={0.5} metalness={0.4} />
      </mesh>
      <mesh position={[0, 0.1, -0.27]}>
        <cylinderGeometry args={[0.09, 0.09, 0.03, 14]} />
        <meshStandardMaterial color="#9299b0" roughness={0.6} metalness={0.3} />
      </mesh>

      {/* panning head */}
      <group ref={head}>
        <RoundedBox args={[0.24, 0.22, 0.62]} radius={0.05} position={[0, 0, 0.22]}>
          <meshStandardMaterial
            color={dead ? '#a9aec0' : '#f4f6fb'}
            roughness={0.4}
            metalness={0.25}
            emissive={selected ? '#7c5cf0' : hovered ? '#9d8cf5' : '#000000'}
            emissiveIntensity={selected ? 0.35 : hovered ? 0.3 : 0}
          />
        </RoundedBox>
        {/* generous invisible hit-area so the small camera is easy to hover/click */}
        <mesh
          visible={false}
          position={[0, 0, 0.35]}
          onClick={(e) => { e.stopPropagation(); select('camera_01') }}
          onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer' }}
          onPointerOut={() => { setHovered(false); document.body.style.cursor = 'auto' }}
        >
          <boxGeometry args={[1.2, 1.0, 1.7]} />
        </mesh>
        {/* sun hood */}
        <mesh position={[0, 0.09, 0.56]}>
          <boxGeometry args={[0.26, 0.03, 0.18]} />
          <meshStandardMaterial color={dead ? '#9aa0b4' : '#dfe4ee'} roughness={0.5} />
        </mesh>
        {/* lens barrel + glass */}
        <mesh position={[0, 0, 0.56]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.085, 0.095, 0.09, 20]} />
          <meshStandardMaterial color="#3a3f52" roughness={0.3} metalness={0.5} />
        </mesh>
        <mesh ref={lens} position={[0, 0, 0.61]}>
          <circleGeometry args={[0.062, 20]} />
          <meshStandardMaterial color="#1c2233" emissive="#5fa8ff" emissiveIntensity={0.9} roughness={0.15} metalness={0.4} />
        </mesh>
        {/* status LED */}
        <mesh ref={led} position={[0.085, 0.135, 0.3]}>
          <sphereGeometry args={[0.02, 10, 10]} />
          <meshStandardMaterial color="#34f5a5" emissive="#1fd489" emissiveIntensity={1.6} />
        </mesh>
        {/* scanning cone */}
        <mesh ref={cone} position={[0, 0, 1.7]} rotation={[-Math.PI / 2, 0, 0]}>
          <coneGeometry args={[0.85, 2.3, 24, 1, true]} />
          <meshBasicMaterial color="#7fb0ff" transparent opacity={0.045} side={THREE.DoubleSide} depthWrite={false} blending={THREE.AdditiveBlending} />
        </mesh>
      </group>

      <pointLight ref={glow} position={[0, 0.1, 0.7]} color="#8fb0ff" intensity={1.6} distance={3.2} decay={2} />

      {warning && !dead && (
        <Sparkles count={42} scale={[1.6, 1.2, 1.6]} position={[0, 0.1, 0.4]} size={3.4} speed={2.6} color="#ff8a3d" opacity={0.9} />
      )}

      {/* floating device tag */}
      <Html position={[0, 0.62, 0.2]} center zIndexRange={[30, 0]}>
        <div className={`tag-chip ${warning ? 'warn' : ''} ${dead ? 'off' : ''}`}>
          {dead ? (
            <>◼ <span className="chip-name">客厅摄像头</span><span className="chip-status">· 已隔离</span></>
          ) : warning ? (
            <><span className="r">▲</span><span className="chip-name">客厅摄像头</span><span className="chip-status">· 可疑 {Math.round(risk * 100)}%</span></>
          ) : (
            <><span className="g">●</span><span className="chip-name">客厅摄像头</span><span className="chip-status">· 安全</span></>
          )}
        </div>
      </Html>
    </group>
  )
}
