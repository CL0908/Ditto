// Shared spatial layout for the apartment (world units ~ meters)
export const LAYOUT = {
  room: { w: 10.4, d: 9.4, h: 5 },
  // wall camera above the back-wall window, pointing into the room (+z)
  camera: { pos: [-1.6, 3.62, -4.42], rotY: 0 },
  // pendant above the coffee table
  light: { pos: [1.7, 4.32, -0.25] },
  // smart plug on the back wall, right of the TV console
  plug: { pos: [3.6, 0.52, -4.68] },
  // TV panel on the back wall above its console, facing the sofa (+z)
  tv: { pos: [1.8, 1.72, -4.64] },
  // Tito hovers between the sofa and the TV
  guardian: { pos: [1.8, 2.02, -1.9] },
  cloud: { pos: [0.2, 6.35, -2.2] },
  intruder: { pos: [6.9, 5.3, 2.6] },
}

export const VIEWS = {
  overview: { pos: [7.4, 5.3, 8.9], tgt: [0, 1.3, -0.6] },
  camera_01: { pos: [-1.6, 2.4, -1.4], tgt: [-1.6, 3.5, -4.35] },
  guardian: { pos: [3.4, 2.8, 1.6], tgt: [1.8, 2.0, -1.9] },
  light_01: { pos: [1.7, 1.7, 2.4], tgt: [1.7, 2.9, -0.25] },
  plug_01: { pos: [3.2, 1.5, -2.2], tgt: [3.6, 0.6, -4.6] },
}
