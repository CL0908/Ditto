import { Suspense, useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, RoundedBox, Sparkles } from '@react-three/drei'
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import { useSecurityStore, selectThreatLevel } from '../state/store.js'
import { LAYOUT, VIEWS } from '../lib/layout.js'
import CameraDevice from './CameraDevice.jsx'
import ZigbeeLight from './ZigbeeLight.jsx'
import SmartPlug from './SmartPlug.jsx'
import TitoGuardian from './TitoGuardian.jsx'
import BeamSky from './BeamSky.jsx'
import NetworkGraph from './NetworkGraph.jsx'

/* Cinematic camera: glides to a view when selection changes, then hands full
   control to the user (OrbitControls). Any manual orbit input cancels the glide. */
function CameraRig() {
  const controls = useRef()
  const selected = useSecurityStore((s) => s.selected)
  const { camera } = useThree()
  const animating = useRef(true)
  const tmpPos = useMemo(() => new THREE.Vector3(), [])
  const tmpTgt = useMemo(() => new THREE.Vector3(), [])

  // A selection change (device click / Overview button / empty-space click)
  // triggers exactly one glide to the new view.
  useEffect(() => {
    animating.current = true
  }, [selected])

  useFrame((_, dt) => {
    if (!animating.current) return
    const view = VIEWS[selected] || VIEWS.overview
    const k = 2.6
    camera.position.x = THREE.MathUtils.damp(camera.position.x, view.pos[0], k, dt)
    camera.position.y = THREE.MathUtils.damp(camera.position.y, view.pos[1], k, dt)
    camera.position.z = THREE.MathUtils.damp(camera.position.z, view.pos[2], k, dt)
    const t = controls.current?.target
    if (t) {
      t.x = THREE.MathUtils.damp(t.x, view.tgt[0], k, dt)
      t.y = THREE.MathUtils.damp(t.y, view.tgt[1], k, dt)
      t.z = THREE.MathUtils.damp(t.z, view.tgt[2], k, dt)
      controls.current.update()
    }
    // Arrived? Release control so the user orbits freely.
    tmpPos.set(...view.pos)
    tmpTgt.set(...view.tgt)
    if (camera.position.distanceTo(tmpPos) < 0.04 && (!t || t.distanceTo(tmpTgt) < 0.04)) {
      animating.current = false
    }
  })

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enablePan={false}
      enableDamping
      dampingFactor={0.08}
      rotateSpeed={0.85}
      zoomSpeed={0.9}
      minDistance={2.2}
      maxDistance={20}
      maxPolarAngle={Math.PI / 2.02}
      target={VIEWS.overview.tgt}
      onStart={() => { animating.current = false }}
    />
  )
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.75} color="#ffffff" />
      <hemisphereLight args={['#f4f1ff', '#b3aad4', 0.9]} />
      <directionalLight position={[6, 9, 3]} intensity={1.6} color="#fff1dc" />
      {/* soft lavender fill from the right to keep shadows gentle */}
      <directionalLight position={[-7, 5, 6]} intensity={0.55} color="#c9b8f5" />
    </>
  )
}

/* Red emergency wash that fades in while a threat is active */
function AlertLight() {
  const ref = useRef()
  const level = useSecurityStore(selectThreatLevel)
  useFrame(({ clock }) => {
    if (!ref.current) return
    const target = level === 'threat' ? 26 + Math.sin(clock.elapsedTime * 6) * 12 : 0
    ref.current.intensity = THREE.MathUtils.lerp(ref.current.intensity, target, 0.08)
  })
  return <pointLight ref={ref} position={[0, 4.4, 0.5]} color="#ff4455" distance={14} decay={2} intensity={0} />
}

function Room() {
  const { w, d, h } = LAYOUT.room
  return (
    <group>
      {/* floor */}
      <mesh position={[0, -0.05, 0]}>
        <boxGeometry args={[w, 0.1, d]} />
        <meshStandardMaterial color="#e7e1f2" roughness={0.95} metalness={0} />
      </mesh>
      <gridHelper args={[10.2, 26, '#c9bfe4', '#d8d1ec']} position={[0, 0.005, 0]} scale={[1, 1, 9.2 / 10.2]} />

      {/* rug — under the sofa + coffee table zone */}
      <RoundedBox args={[3.6, 0.024, 2.6]} radius={0.012} position={[1.35, 0.012, 0.55]}>
        <meshStandardMaterial color="#d5caeb" roughness={1} />
      </RoundedBox>

      {/* back + left walls */}
      <mesh position={[0, h / 2, -d / 2 - 0.06]}>
        <boxGeometry args={[w, h, 0.12]} />
        <meshStandardMaterial color="#f4f1fa" roughness={0.95} />
      </mesh>
      <mesh position={[-w / 2 - 0.06, h / 2, 0]}>
        <boxGeometry args={[0.12, h, d]} />
        <meshStandardMaterial color="#ece7f6" roughness={0.95} />
      </mesh>

      {/* baseboard glow strips */}
      <mesh position={[0, 0.045, -d / 2 + 0.02]}>
        <boxGeometry args={[w - 0.3, 0.03, 0.02]} />
        <meshBasicMaterial color="#a78bfa" />
      </mesh>
      <mesh position={[-w / 2 + 0.02, 0.045, 0]}>
        <boxGeometry args={[0.02, 0.03, d - 0.3]} />
        <meshBasicMaterial color="#a78bfa" />
      </mesh>

    </group>
  )
}

/* TV on the back wall with a low console bench, speaker and plants */
function TVUnit() {
  const screen = useRef()
  useFrame(({ clock }) => {
    if (screen.current) {
      screen.current.emissiveIntensity = 0.55 + Math.sin(clock.elapsedTime * 1.7) * 0.1
    }
  })
  return (
    <group>
      {/* console bench */}
      <RoundedBox args={[2.6, 0.42, 0.48]} radius={0.03} position={[1.8, 0.27, -4.42]}>
        <meshStandardMaterial color="#e3dcf1" roughness={0.55} metalness={0.15} />
      </RoundedBox>
      {/* stand */}
      <mesh position={[1.8, 0.66, -4.55]}>
        <boxGeometry args={[0.5, 0.36, 0.12]} />
        <meshStandardMaterial color="#37324e" roughness={0.4} metalness={0.4} />
      </mesh>
      {/* TV panel — faces the sofa (+z) */}
      <group position={LAYOUT.tv.pos}>
        <RoundedBox args={[2.1, 1.2, 0.07]} radius={0.02}>
          <meshStandardMaterial color="#37324e" roughness={0.4} metalness={0.4} />
        </RoundedBox>
        <mesh ref={screen} position={[0, 0, 0.045]}>
          <planeGeometry args={[1.96, 1.06]} />
          <meshStandardMaterial color="#241f3a" emissive="#7f9fe8" emissiveIntensity={0.55} roughness={0.4} />
        </mesh>
      </group>
      {/* speaker */}
      <mesh position={[2.9, 0.73, -4.42]}>
        <cylinderGeometry args={[0.09, 0.09, 0.5, 16]} />
        <meshStandardMaterial color="#4a4368" roughness={0.5} metalness={0.3} />
      </mesh>
      {/* console plants */}
      {[0.75, 2.35].map((x) => (
        <group key={x} position={[x, 0.48, -4.42]}>
          <mesh position={[0, 0.05, 0]}>
            <cylinderGeometry args={[0.07, 0.09, 0.1, 12]} />
            <meshStandardMaterial color="#f0ebf8" roughness={0.8} />
          </mesh>
          <mesh position={[0, 0.2, 0]}>
            <icosahedronGeometry args={[0.11, 1]} />
            <meshStandardMaterial color="#8fce9f" roughness={0.9} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

/* Raised diorama base with glowing edge strips and an endlessly
   scrolling TITO marquee around the skirt faces */
function Platform() {
  // "TITO · TITO ·" painted on a canvas, tiled seamlessly so the
  // texture offset can advance forever without a visible seam
  const marqueeTex = useMemo(() => {
    const c = document.createElement('canvas')
    c.width = 1024
    c.height = 128
    const ctx = c.getContext('2d')
    ctx.fillStyle = '#cab8ff'
    ctx.font = '700 72px "Segoe UI", system-ui, sans-serif'
    ctx.textBaseline = 'middle'
    for (let x = 0; x < c.width; x += 256) {
      ctx.fillText('TITO', x + 34, c.height / 2 + 4)
      ctx.beginPath()
      ctx.arc(x + 224, c.height / 2, 7, 0, Math.PI * 2)
      ctx.fill()
    }
    const t = new THREE.CanvasTexture(c)
    t.wrapS = THREE.RepeatWrapping
    t.repeat.x = 2
    t.anisotropy = 4
    return t
  }, [])

  const marqueeMat = useMemo(
    () => new THREE.MeshBasicMaterial({ map: marqueeTex, transparent: true, toneMapped: false, depthWrite: false }),
    [marqueeTex]
  )

  // advance the ticker forever (~1 full pattern every 8s)
  useFrame((_, dt) => {
    marqueeTex.offset.x = (marqueeTex.offset.x + dt * 0.12) % 1
  })

  return (
    <group>
      <mesh position={[0, -0.255, 0]}>
        <boxGeometry args={[11.3, 0.5, 10.3]} />
        <meshStandardMaterial color="#453d63" roughness={0.6} metalness={0.1} />
      </mesh>
      {/* top-edge glow strips */}
      {[5.09, -5.09].map((z) => (
        <mesh key={z} position={[0, 0.001, z]}>
          <boxGeometry args={[11.26, 0.024, 0.06]} />
          <meshBasicMaterial color="#b9a3fd" toneMapped={false} />
        </mesh>
      ))}
      {[5.59, -5.59].map((x) => (
        <mesh key={x} position={[x, 0.001, 0]}>
          <boxGeometry args={[0.06, 0.024, 10.26]} />
          <meshBasicMaterial color="#b9a3fd" toneMapped={false} />
        </mesh>
      ))}
      {/* endless TITO marquee scrolling around all four skirt faces */}
      <mesh position={[0, -0.26, 5.158]} material={marqueeMat}>
        <planeGeometry args={[11.3, 0.4]} />
      </mesh>
      <mesh position={[0, -0.26, -5.158]} rotation={[0, Math.PI, 0]} material={marqueeMat}>
        <planeGeometry args={[11.3, 0.4]} />
      </mesh>
      <mesh position={[5.658, -0.26, 0]} rotation={[0, Math.PI / 2, 0]} material={marqueeMat}>
        <planeGeometry args={[10.3, 0.4]} />
      </mesh>
      <mesh position={[-5.658, -0.26, 0]} rotation={[0, -Math.PI / 2, 0]} material={marqueeMat}>
        <planeGeometry args={[10.3, 0.4]} />
      </mesh>
    </group>
  )
}

/* Purple LED cove along the top edge of both walls */
function CoveStrips() {
  return (
    <group>
      <mesh position={[0, 4.88, -4.67]}>
        <boxGeometry args={[10.3, 0.05, 0.05]} />
        <meshBasicMaterial color="#c4b5fd" toneMapped={false} />
      </mesh>
      <mesh position={[-5.17, 4.88, 0]}>
        <boxGeometry args={[0.05, 0.05, 9.3]} />
        <meshBasicMaterial color="#c4b5fd" toneMapped={false} />
      </mesh>
    </group>
  )
}

/* Window with venetian blinds on the back wall (camera mounts above it) */
function BackWindowBlinds() {
  return (
    <group position={[-1.6, 0, 0]}>
      <RoundedBox args={[1.8, 2.0, 0.1]} radius={0.02} position={[0, 2.3, -4.68]}>
        <meshStandardMaterial color="#f4f1fa" roughness={0.7} />
      </RoundedBox>
      <mesh position={[0, 2.3, -4.63]}>
        <planeGeometry args={[1.6, 1.8]} />
        <meshStandardMaterial color="#d5e2f8" emissive="#b9ccf0" emissiveIntensity={0.3} roughness={0.4} />
      </mesh>
      {Array.from({ length: 7 }, (_, i) => (
        <mesh key={i} position={[0, 3.02 - i * 0.235, -4.6]} rotation={[0.18, 0, 0]}>
          <boxGeometry args={[1.62, 0.15, 0.02]} />
          <meshStandardMaterial color="#e9e4f6" roughness={0.85} />
        </mesh>
      ))}
      <mesh position={[0, 3.4, -4.63]}>
        <boxGeometry args={[1.84, 0.14, 0.16]} />
        <meshStandardMaterial color="#ded6ee" roughness={0.7} />
      </mesh>
    </group>
  )
}

/* Workstation corner: desk + monitor + lamp + chair against the left wall */
function DeskCorner() {
  return (
    <group>
      {/* desktop */}
      <RoundedBox args={[0.75, 0.06, 2.0]} radius={0.015} position={[-4.82, 0.98, -1.2]}>
        <meshStandardMaterial color="#f5f2fb" roughness={0.4} metalness={0.1} />
      </RoundedBox>
      {/* end panels */}
      {[-2.12, -0.28].map((z) => (
        <mesh key={z} position={[-4.82, 0.48, z]}>
          <boxGeometry args={[0.7, 0.94, 0.05]} />
          <meshStandardMaterial color="#e3dcf1" roughness={0.6} />
        </mesh>
      ))}
      {/* monitor — faces the chair (+x) */}
      <group position={[-4.55, 1.32, -1.35]}>
        <RoundedBox args={[0.04, 0.42, 0.68]} radius={0.01}>
          <meshStandardMaterial color="#37324e" roughness={0.4} metalness={0.4} />
        </RoundedBox>
        <mesh position={[0.025, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
          <planeGeometry args={[0.62, 0.36]} />
          <meshStandardMaterial color="#241f3a" emissive="#8b5cf6" emissiveIntensity={0.6} roughness={0.4} />
        </mesh>
      </group>
      <mesh position={[-4.62, 1.11, -1.35]}>
        <boxGeometry args={[0.14, 0.24, 0.08]} />
        <meshStandardMaterial color="#4a4368" roughness={0.5} metalness={0.3} />
      </mesh>
      <mesh position={[-4.62, 1.0, -1.35]}>
        <boxGeometry args={[0.22, 0.02, 0.3]} />
        <meshStandardMaterial color="#4a4368" roughness={0.5} metalness={0.3} />
      </mesh>
      {/* keyboard + mouse */}
      <RoundedBox args={[0.17, 0.025, 0.52]} radius={0.008} position={[-4.28, 1.02, -1.3]}>
        <meshStandardMaterial color="#ded6ee" roughness={0.6} />
      </RoundedBox>
      <RoundedBox args={[0.1, 0.03, 0.07]} radius={0.012} position={[-4.28, 1.02, -0.72]}>
        <meshStandardMaterial color="#ded6ee" roughness={0.6} />
      </RoundedBox>
      {/* desk lamp */}
      <mesh position={[-4.75, 1.02, -1.95]}>
        <cylinderGeometry args={[0.09, 0.11, 0.03, 14]} />
        <meshStandardMaterial color="#8d84a8" roughness={0.5} metalness={0.3} />
      </mesh>
      <mesh position={[-4.72, 1.22, -1.92]} rotation={[0, 0, -0.35]}>
        <cylinderGeometry args={[0.015, 0.015, 0.42, 8]} />
        <meshStandardMaterial color="#8d84a8" roughness={0.5} metalness={0.3} />
      </mesh>
      <mesh position={[-4.64, 1.44, -1.88]}>
        <sphereGeometry args={[0.06, 12, 12]} />
        <meshBasicMaterial color="#ffe3b3" toneMapped={false} />
      </mesh>
      {/* chair */}
      <group position={[-3.95, 0, -1.25]}>
        <RoundedBox args={[0.5, 0.07, 0.55]} radius={0.03} position={[0, 0.6, 0]}>
          <meshStandardMaterial color="#cfc5e8" roughness={0.9} />
        </RoundedBox>
        <RoundedBox args={[0.07, 0.62, 0.5]} radius={0.03} position={[0.26, 0.98, 0]}>
          <meshStandardMaterial color="#bfb2e0" roughness={0.9} />
        </RoundedBox>
        <mesh position={[0, 0.36, 0]}>
          <cylinderGeometry args={[0.035, 0.035, 0.42, 10]} />
          <meshStandardMaterial color="#8d84a8" roughness={0.5} metalness={0.4} />
        </mesh>
        <mesh position={[0, 0.03, 0]}>
          <cylinderGeometry args={[0.3, 0.32, 0.05, 18]} />
          <meshStandardMaterial color="#8d84a8" roughness={0.5} metalness={0.4} />
        </mesh>
      </group>
    </group>
  )
}

const BOOK_COLORS = ['#b8a9e8', '#e8a9b8', '#a9c8e8', '#a9e8c3', '#e8d8a9', '#d0c4ec']

/* Bookshelf with books and plants on top, against the left wall */
function Bookshelf() {
  const frame = '#ded6ee'
  return (
    <group position={[-4.95, 0, -3.2]}>
      {/* side panels */}
      {[-0.975, 0.975].map((z) => (
        <mesh key={z} position={[0, 0.96, z]}>
          <boxGeometry args={[0.34, 1.92, 0.05]} />
          <meshStandardMaterial color={frame} roughness={0.65} />
        </mesh>
      ))}
      {/* shelves with books */}
      {[0.14, 0.64, 1.14, 1.64].map((y, s) => (
        <group key={y}>
          <mesh position={[0, y, 0]}>
            <boxGeometry args={[0.32, 0.05, 1.9]} />
            <meshStandardMaterial color={frame} roughness={0.65} />
          </mesh>
          {s < 3 &&
            Array.from({ length: 7 }, (_, i) => {
              const h = 0.24 + ((i * 7 + s * 3) % 4) * 0.03
              const w = 0.09 + ((i * 5 + s) % 3) * 0.035
              const z = -0.78 + i * 0.26 + (s % 2) * 0.05
              return (
                <mesh key={i} position={[0, y + 0.025 + h / 2, z]} rotation={[(i + s) % 5 === 4 ? -0.14 : 0, 0, 0]}>
                  <boxGeometry args={[0.2, h, w]} />
                  <meshStandardMaterial color={BOOK_COLORS[(i + s * 2) % BOOK_COLORS.length]} roughness={0.8} />
                </mesh>
              )
            })}
        </group>
      ))}
      {/* top panel + trailing plants */}
      <mesh position={[0, 1.92, 0]}>
        <boxGeometry args={[0.34, 0.05, 2.0]} />
        <meshStandardMaterial color={frame} roughness={0.65} />
      </mesh>
      {[-0.68, 0.05, 0.7].map((z, i) => (
        <group key={z} position={[0, 1.945, z]}>
          <mesh position={[0, 0.06, 0]}>
            <cylinderGeometry args={[0.08, 0.1, 0.12, 12]} />
            <meshStandardMaterial color="#f0ebf8" roughness={0.8} />
          </mesh>
          <mesh position={[0, 0.22 + i * 0.02, 0]}>
            <icosahedronGeometry args={[0.13, 1]} />
            <meshStandardMaterial color="#8fce9f" roughness={0.9} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

/* Cylindrical air purifier beside the sofa */
function AirPurifier() {
  return (
    <group position={[0.25, 0, 1.3]}>
      <mesh position={[0, 0.33, 0]}>
        <cylinderGeometry args={[0.2, 0.22, 0.62, 20]} />
        <meshStandardMaterial color="#f4f6fb" roughness={0.5} metalness={0.1} />
      </mesh>
      <mesh position={[0, 0.66, 0]}>
        <cylinderGeometry args={[0.17, 0.18, 0.05, 20]} />
        <meshStandardMaterial color="#d9d2ea" roughness={0.5} />
      </mesh>
      <mesh position={[0, 0.45, 0.21]}>
        <sphereGeometry args={[0.022, 8, 8]} />
        <meshBasicMaterial color="#22b47e" toneMapped={false} />
      </mesh>
    </group>
  )
}

/* Soft round pouf on the rug corner */
function Pouf() {
  return (
    <group position={[0.5, 0, -0.2]}>
      <mesh position={[0, 0.16, 0]}>
        <cylinderGeometry args={[0.34, 0.36, 0.3, 20]} />
        <meshStandardMaterial color="#c9bce6" roughness={0.95} />
      </mesh>
      <mesh position={[0, 0.32, 0]}>
        <cylinderGeometry args={[0.3, 0.33, 0.08, 20]} />
        <meshStandardMaterial color="#bfb2e0" roughness={0.95} />
      </mesh>
    </group>
  )
}

function Sofa() {
  const fabric = '#cfc5e8'
  const cushion = '#bfb2e0'
  return (
    <group position={[1.8, 0, 1.3]}>
      <RoundedBox args={[2.4, 0.34, 1.0]} radius={0.08} position={[0, 0.3, 0]}>
        <meshStandardMaterial color={fabric} roughness={0.9} />
      </RoundedBox>
      <RoundedBox args={[2.4, 0.66, 0.26]} radius={0.08} position={[0, 0.68, 0.55]}>
        <meshStandardMaterial color={fabric} roughness={0.9} />
      </RoundedBox>
      {[-1.12, 1.12].map((x) => (
        <RoundedBox key={x} args={[0.26, 0.36, 1.0]} radius={0.08} position={[x, 0.6, 0]}>
          <meshStandardMaterial color={fabric} roughness={0.9} />
        </RoundedBox>
      ))}
      {[-0.55, 0.55].map((x) => (
        <RoundedBox key={x} args={[1.0, 0.16, 0.86]} radius={0.06} position={[x, 0.56, 0.02]}>
          <meshStandardMaterial color={cushion} roughness={0.95} />
        </RoundedBox>
      ))}
    </group>
  )
}

function CoffeeTable() {
  return (
    <group position={[1.7, 0, -0.25]}>
      <RoundedBox args={[1.05, 0.05, 0.6]} radius={0.015} position={[0, 0.4, 0]}>
        <meshStandardMaterial color="#f5f2fb" roughness={0.3} metalness={0.2} />
      </RoundedBox>
      {[
        [-0.45, -0.22],
        [0.45, -0.22],
        [-0.45, 0.22],
        [0.45, 0.22],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.2, z]}>
          <cylinderGeometry args={[0.02, 0.02, 0.4, 8]} />
          <meshStandardMaterial color="#b3a8d4" roughness={0.5} metalness={0.3} />
        </mesh>
      ))}
      {/* book + tiny succulent */}
      <RoundedBox args={[0.28, 0.045, 0.2]} radius={0.01} position={[-0.18, 0.45, -0.08]} rotation={[0, 0.35, 0]}>
        <meshStandardMaterial color="#8b5cf6" roughness={0.7} />
      </RoundedBox>
      <group position={[0.25, 0.425, 0.1]}>
        <mesh position={[0, 0.04, 0]}>
          <cylinderGeometry args={[0.05, 0.065, 0.08, 10]} />
          <meshStandardMaterial color="#f0ebf8" roughness={0.8} />
        </mesh>
        <mesh position={[0, 0.13, 0]}>
          <icosahedronGeometry args={[0.07, 1]} />
          <meshStandardMaterial color="#8fce9f" roughness={0.9} />
        </mesh>
      </group>
    </group>
  )
}

export default function SmartHomeScene() {
  const select = useSecurityStore((s) => s.select)

  return (
    <div className="scene-wrap">
      <Canvas
        camera={{ position: VIEWS.overview.pos, fov: 48, near: 0.1, far: 80 }}
      gl={{ antialias: true }}
      dpr={[1, 1.75]}
      onPointerMissed={() => select(null)}
    >
      <BeamSky />
      <fog attach="fog" args={['#c9ccea', 16, 34]} />

      <Suspense fallback={null}>
        <Lights />
        <AlertLight />
        <Room />
        <Platform />
        <CoveStrips />
        <BackWindowBlinds />
        <TVUnit />
        <DeskCorner />
        <Bookshelf />
        <Sofa />
        <CoffeeTable />
        <AirPurifier />
        <Pouf />

        <CameraDevice />
        <ZigbeeLight />
        <SmartPlug />
        <TitoGuardian />
        <NetworkGraph />

        {/* ambient dust for depth */}
        <Sparkles count={70} scale={[10, 5, 9]} position={[0, 2.4, 0]} size={1.1} speed={0.18} color="#a78bfa" opacity={0.55} />
      </Suspense>

      <CameraRig />

        <EffectComposer>
          <Bloom mipmapBlur intensity={0.45} luminanceThreshold={0.62} luminanceSmoothing={0.35} />
          <Vignette eskil={false} offset={0.28} darkness={0.32} />
        </EffectComposer>
      </Canvas>
    </div>
  )
}
