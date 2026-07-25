import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame, useThree } from '@react-three/fiber'

/**
 * BeamSky — light-pastel "aurora beams" backdrop.
 *
 * Adapted from the classic dark beams-background effect, re-tuned for the
 * light theme: soft violet/blue light rays drift upward over a periwinkle
 * wash. Drawn on a low-res offscreen canvas each frame and used as the
 * three.js scene background (cheap, and keeps Bloom + fog compositing intact).
 */

const W = 512
const H = 288
const BEAM_COUNT = 22

function makeBeam() {
  return {
    x: Math.random() * W * 1.4 - W * 0.2,
    y: Math.random() * H * 1.4 - H * 0.2,
    width: 14 + Math.random() * 26,
    length: H * 2.2,
    angle: ((-35 + Math.random() * 10) * Math.PI) / 180,
    speed: 9 + Math.random() * 22,          // px/sec (canvas space)
    opacity: 0.1 + Math.random() * 0.14,
    hue: 228 + Math.random() * 52,          // blue → violet, palette family
    pulse: Math.random() * Math.PI * 2,
    pulseSpeed: 0.5 + Math.random() * 0.9,  // rad/sec
  }
}

function respawn(b) {
  b.y = H + 40
  b.x = Math.random() * W * 1.2 - W * 0.1
  b.width = 14 + Math.random() * 26
  b.speed = 9 + Math.random() * 22
  b.hue = 228 + Math.random() * 52
  b.opacity = 0.1 + Math.random() * 0.14
}

export default function BeamSky() {
  const scene = useThree((s) => s.scene)
  const beams = useRef(Array.from({ length: BEAM_COUNT }, makeBeam))

  const { ctx, tex } = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext('2d')
    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    return { ctx, tex }
  }, [])

  useEffect(() => {
    scene.background = tex
    return () => {
      scene.background = null
      tex.dispose()
    }
  }, [scene, tex])

  useFrame(({ clock }, dt) => {
    const t = clock.elapsedTime
    // base wash — light periwinkle gradient
    const base = ctx.createLinearGradient(0, 0, 0, H)
    base.addColorStop(0, '#d2d5f2')
    base.addColorStop(1, '#c1c4e8')
    ctx.filter = 'none'
    ctx.fillStyle = base
    ctx.fillRect(0, 0, W, H)

    // slow "breathing" of the whole beam field
    const breathe = 0.85 + Math.sin(t * 0.25) * 0.15

    ctx.filter = 'blur(5px)'
    for (const b of beams.current) {
      b.y -= b.speed * dt
      b.pulse += b.pulseSpeed * dt
      if (b.y + b.length < -40) respawn(b)

      const a = b.opacity * (0.8 + Math.sin(b.pulse) * 0.2) * breathe
      const col = (alpha) => `hsla(${b.hue}, 72%, 71%, ${alpha})`

      ctx.save()
      ctx.translate(b.x, b.y)
      ctx.rotate(b.angle)
      const g = ctx.createLinearGradient(0, 0, 0, b.length)
      g.addColorStop(0, col(0))
      g.addColorStop(0.1, col(a * 0.5))
      g.addColorStop(0.4, col(a))
      g.addColorStop(0.6, col(a))
      g.addColorStop(0.9, col(a * 0.5))
      g.addColorStop(1, col(0))
      ctx.fillStyle = g
      ctx.fillRect(-b.width / 2, 0, b.width, b.length)
      ctx.restore()
    }
    ctx.filter = 'none'
    tex.needsUpdate = true
  })

  return null
}
