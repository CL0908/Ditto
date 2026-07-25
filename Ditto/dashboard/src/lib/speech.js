// Tito Guardian voice — Web Speech API, safely degraded when unavailable
export function speak(text) {
  try {
    if (!('speechSynthesis' in window)) return
    const synth = window.speechSynthesis
    synth.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = 1.02
    u.pitch = 0.85
    u.volume = 0.9
    const voices = synth.getVoices()
    const preferred =
      voices.find((v) => /zh[-_]CN/i.test(v.lang) && /xiaoxiao|huihui|yunjian|kangkang|google/i.test(v.name)) ||
      voices.find((v) => /zh[-_]CN/i.test(v.lang)) ||
      voices.find((v) => /^zh/i.test(v.lang))
    if (preferred) u.voice = preferred
    synth.speak(u)
  } catch {
    /* audio not available — visual bubble still communicates */
  }
}
