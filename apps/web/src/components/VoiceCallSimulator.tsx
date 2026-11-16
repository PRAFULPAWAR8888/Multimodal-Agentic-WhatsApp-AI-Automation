import { useState, useRef, useEffect } from 'react'
import { 
  Phone, PhoneOff, Mic, MicOff, Square, 
  Sparkles, Send, Volume2 
} from 'lucide-react'

interface VoiceCallSimulatorProps {
  onCallTranscript?: (role: 'user' | 'ai', text: string) => void
  onCallEnded?: () => void
}

type CallTranscriptItem = {
  id: string
  speaker: 'Caller' | 'Anand'
  text: string
  time: string
}

export default function VoiceCallSimulator({ onCallTranscript }: VoiceCallSimulatorProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [isAiSpeaking, setIsAiSpeaking] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [currentMode, setCurrentMode] = useState<'ptt' | 'hands-free'>('ptt')
  const [isPttActive, setIsPttActive] = useState(false)
  const [vuPercent, setVuPercent] = useState(0)
  const [callSeconds, setCallSeconds] = useState(0)
  const [statusText, setStatusText] = useState('Ready to start call')
  const [transcripts, setTranscripts] = useState<CallTranscriptItem[]>([
    {
      id: 'welcome',
      speaker: 'Anand',
      text: 'Hello! I am Anand Kumar representing Associative. Click Call to speak with me live.',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ])
  const [customText, setCustomText] = useState('')
  const [isSimulatingSpeech, setIsSimulatingSpeech] = useState(false)

  // Audio & WebSocket refs
  const wsRef = useRef<WebSocket | null>(null)
  const streamSidRef = useRef<string | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null)
  const nextPlayTimeRef = useRef<number>(0)
  const callTimerRef = useRef<any>(null)
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  // State refs to access fresh values inside ScriptProcessorNode callback
  const isConnectedRef = useRef(false)
  const isMutedRef = useRef(false)
  const isAiSpeakingRef = useRef(false)
  const currentModeRef = useRef<'ptt' | 'hands-free'>('ptt')
  const isPttActiveRef = useRef(false)

  useEffect(() => {
    isConnectedRef.current = isConnected
  }, [isConnected])

  useEffect(() => {
    isMutedRef.current = isMuted
  }, [isMuted])

  useEffect(() => {
    isAiSpeakingRef.current = isAiSpeaking
  }, [isAiSpeaking])

  useEffect(() => {
    currentModeRef.current = currentMode
  }, [currentMode])

  useEffect(() => {
    isPttActiveRef.current = isPttActive
  }, [isPttActive])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcripts])

  // Keyboard listener for Spacebar Push-to-Talk
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.code === 'Space' && 
        currentModeRef.current === 'ptt' && 
        isConnectedRef.current && 
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault()
        triggerPttStart()
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      if (
        e.code === 'Space' && 
        currentModeRef.current === 'ptt' && 
        isConnectedRef.current && 
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault()
        triggerPttStop()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      cleanUpCall()
    }
  }, [])

  // Audio Decoding (Mu-Law to 32-bit Linear PCM)
  const mulawToFloat = (mulawBytes: Uint8Array): Float32Array => {
    const pcm = new Float32Array(mulawBytes.length)
    for (let i = 0; i < mulawBytes.length; i++) {
      const u = ~mulawBytes[i] & 0xff
      const sign = u & 0x80
      const exponent = (u >> 4) & 0x07
      const mantissa = u & 0x0f
      let sample = ((mantissa << 3) + 0x84) << exponent
      sample -= 0x84
      sample = sign ? -sample : sample
      pcm[i] = sample / 32768.0
    }
    return pcm
  }

  // Audio Encoding (Float sample to 8-bit Mu-Law)
  const floatToMulaw = (sample: number): number => {
    const BIAS = 0x84
    const CLIP = 32635
    const s = Math.max(-1, Math.min(1, sample))
    let intSample = Math.floor(s * 32767)
    const sign = intSample < 0 ? 0x80 : 0
    if (intSample < 0) intSample = -intSample
    if (intSample > CLIP) intSample = CLIP
    intSample += BIAS
    let exponent = 7
    for (let expMask = 0x4000; (intSample & expMask) === 0 && exponent > 0; expMask >>= 1) exponent--
    const mantissa = (intSample >> (exponent + 3)) & 0x0f
    return ~(sign | (exponent << 4) | mantissa) & 0xff
  }

  const addTranscript = (speaker: 'Caller' | 'Anand', text: string) => {
    const newItem: CallTranscriptItem = {
      id: Date.now().toString() + Math.random().toString().slice(2, 6),
      speaker,
      text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    setTranscripts(prev => [...prev, newItem])
    if (onCallTranscript) {
      onCallTranscript(speaker === 'Caller' ? 'user' : 'ai', text)
    }
  }

  const startCall = async () => {
    try {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext
      if (!audioCtxRef.current) {
        audioCtxRef.current = new AudioCtxClass()
      }
      if (audioCtxRef.current.state === 'suspended') {
        await audioCtxRef.current.resume()
      }

      setStatusText('Dialing Anand Kumar...')
      const sid = 'web-call-' + Date.now()
      streamSidRef.current = sid

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      // Direct connection to port 8000 when running on dev port 5173
      const wsHost = window.location.port === '5173' ? `${window.location.hostname}:8000` : window.location.host
      const wsUrl = `${wsProtocol}//${wsHost}/ws/twilio/stream`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        setStatusText(currentModeRef.current === 'ptt' ? 'Connected • Hold Space to speak' : 'Connected • Listening to you...')
        
        ws.send(JSON.stringify({ event: 'connected', protocol: 'Call' }))
        ws.send(JSON.stringify({
          event: 'start',
          sequenceNumber: '1',
          start: { streamSid: sid, accountSid: 'AC_web', callSid: 'CA_web_' + Date.now(), tracks: ['inbound'] },
          streamSid: sid
        }))

        setCallSeconds(0)
        clearInterval(callTimerRef.current)
        callTimerRef.current = setInterval(() => {
          setCallSeconds(prev => prev + 1)
        }, 1000)

        startMicrophone()
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.event === 'media' && msg.media?.payload) {
            playIncomingMulaw(msg.media.payload)
          } else if (msg.event === 'transcript') {
            addTranscript(msg.role === 'user' ? 'Caller' : 'Anand', msg.text)
          } else if (msg.event === 'ai_finished' || msg.event === 'clear') {
            if (audioCtxRef.current) {
              nextPlayTimeRef.current = audioCtxRef.current.currentTime
            }
            setIsAiSpeaking(false)
            setStatusText(currentModeRef.current === 'ptt' ? 'Ready • Hold Space to speak' : 'Listening to you...')
          }
        } catch (e) {
          console.error('Telephony WebSocket parse error:', e)
        }
      }

      ws.onclose = () => endCall()
      ws.onerror = (err) => {
        console.error('Telephony WebSocket error:', err)
        setStatusText('Connection error. Please try again.')
        endCall()
      }
    } catch (err) {
      console.error('Failed to start call:', err)
      setStatusText('Failed to start call')
    }
  }

  const startMicrophone = async () => {
    try {
      const audioCtx = audioCtxRef.current
      if (!audioCtx) return

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      })
      mediaStreamRef.current = stream

      const source = audioCtx.createMediaStreamSource(stream)
      const micGain = audioCtx.createGain()
      micGain.gain.value = 1.0 // Clean unity gain

      const scriptNode = audioCtx.createScriptProcessor(2048, 1, 1)
      scriptNodeRef.current = scriptNode

      const downsampleRatio = audioCtx.sampleRate / 8000
      const mulawAccumulator: number[] = []

      scriptNode.onaudioprocess = (e) => {
        if (!isConnectedRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

        const input = e.inputBuffer.getChannelData(0)

        // Calculate live RMS for VU meter
        let sumSquares = 0
        for (let i = 0; i < input.length; i++) {
          sumSquares += input[i] * input[i]
        }
        const rms = Math.sqrt(sumSquares / input.length)
        const pct = Math.min(100, Math.round(rms * 400))

        if (!isMutedRef.current && (currentModeRef.current === 'hands-free' || isPttActiveRef.current)) {
          setVuPercent(pct)
        } else {
          setVuPercent(0)
        }

        // Acoustic Echo Suppression & Push-to-Talk Gates:
        if (isMutedRef.current) return
        if (currentModeRef.current === 'ptt' && !isPttActiveRef.current) return
        if (currentModeRef.current === 'hands-free' && isAiSpeakingRef.current) return // Mic muted while AI speaks!

        for (let i = 0; i < input.length; i += downsampleRatio) {
          let sum = 0
          let count = 0
          const end = Math.min(input.length, Math.floor(i + downsampleRatio))
          for (let k = Math.floor(i); k < end; k++) {
            sum += input[k]
            count++
          }
          const avg = count > 0 ? sum / count : 0
          mulawAccumulator.push(floatToMulaw(avg))

          if (mulawAccumulator.length >= 160) {
            const chunk = new Uint8Array(mulawAccumulator.splice(0, 160))
            let binary = ''
            for (let j = 0; j < chunk.length; j++) binary += String.fromCharCode(chunk[j])
            wsRef.current.send(JSON.stringify({
              event: 'media',
              streamSid: streamSidRef.current,
              media: { payload: btoa(binary) }
            }))
          }
        }
      }

      source.connect(micGain)
      micGain.connect(scriptNode)

      // Prevent local mic feedback into local speakers
      const silentMute = audioCtx.createGain()
      silentMute.gain.value = 0
      scriptNode.connect(silentMute)
      silentMute.connect(audioCtx.destination)
    } catch (err) {
      console.warn('Microphone permission declined or error:', err)
      setStatusText('Mic offline (use preset speech buttons)')
    }
  }

  const playIncomingMulaw = (b64: string) => {
    const audioCtx = audioCtxRef.current
    if (!audioCtx) return

    setIsAiSpeaking(true)
    setStatusText('Anand is speaking...')

    const binary = atob(b64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    const floatPcm = mulawToFloat(bytes)

    // Smooth resample to audioCtx.sampleRate with anti-aliasing
    const targetRate = audioCtx.sampleRate
    const ratio = 8000 / targetRate
    const outLength = Math.round(floatPcm.length / ratio)
    const nativePcm = new Float32Array(outLength)
    for (let i = 0; i < outLength; i++) {
      const srcIdx = i * ratio
      const i0 = Math.floor(srcIdx)
      const i1 = Math.min(i0 + 1, floatPcm.length - 1)
      const frac = srcIdx - i0
      nativePcm[i] = floatPcm[i0] * (1 - frac) + floatPcm[i1] * frac
    }

    const buffer = audioCtx.createBuffer(1, nativePcm.length, targetRate)
    buffer.copyToChannel(nativePcm, 0)

    const src = audioCtx.createBufferSource()
    src.buffer = buffer
    src.connect(audioCtx.destination)

    const now = audioCtx.currentTime
    if (nextPlayTimeRef.current < now) {
      nextPlayTimeRef.current = now + 0.03
    }
    src.start(nextPlayTimeRef.current)
    nextPlayTimeRef.current += buffer.duration

    src.onended = () => {
      if (nextPlayTimeRef.current <= (audioCtxRef.current?.currentTime || 0) + 0.12) {
        setIsAiSpeaking(false)
        setStatusText(currentModeRef.current === 'ptt' ? 'Ready • Hold Space to speak' : 'Listening to you...')
      }
    }
  }

  const triggerPttStart = () => {
    if (!isConnectedRef.current || isPttActiveRef.current) return
    setIsPttActive(true)
    setStatusText('Streaming your voice to Anand...')
  }

  const triggerPttStop = () => {
    if (!isPttActiveRef.current) return
    setIsPttActive(false)
    setStatusText('Anand is thinking...')
    setVuPercent(0)

    // Flush trailing silence to trigger server VAD turn-completion immediately
    if (isConnectedRef.current && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const silenceB64 = btoa(String.fromCharCode(...new Array(160).fill(0xff)))
      for (let i = 0; i < 28; i++) {
        wsRef.current.send(JSON.stringify({
          event: 'media',
          streamSid: streamSidRef.current,
          media: { payload: silenceB64 }
        }))
      }
    }
  }

  const sendManualInterrupt = () => {
    if (!isConnected || !wsRef.current) return
    wsRef.current.send(JSON.stringify({ event: 'interrupt', streamSid: streamSidRef.current }))
    if (audioCtxRef.current) {
      nextPlayTimeRef.current = audioCtxRef.current.currentTime
    }
    setIsAiSpeaking(false)
    setStatusText('Interrupted • Listening...')
  }

  const toggleMute = () => {
    setIsMuted(prev => !prev)
    setVuPercent(0)
  }

  const simulateSpeech = async (text: string) => {
    if (!text.trim() || isSimulatingSpeech) return
    setIsSimulatingSpeech(true)

    if (!isConnected) {
      await startCall()
      await new Promise(r => setTimeout(r, 600))
    }

    addTranscript('Caller', text)
    setStatusText('Transmitting caller audio to Anand...')

    try {
      const resp = await fetch('/api/voice/synthesize-mulaw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      })
      const data = await resp.json()
      if (!data.mulaw_b64) throw new Error(data.error || 'Speech synthesis failed')

      const rawMulaw = atob(data.mulaw_b64)
      const chunkSize = 160
      for (let i = 0; i < rawMulaw.length; i += chunkSize) {
        const slice = rawMulaw.slice(i, i + chunkSize)
        wsRef.current?.send(JSON.stringify({
          event: 'media',
          streamSid: streamSidRef.current,
          media: { payload: btoa(slice) }
        }))
        await new Promise(r => setTimeout(r, 5))
      }

      // Flush silence to trigger server VAD
      const silenceB64 = btoa(String.fromCharCode(...new Array(160).fill(0xff)))
      for (let j = 0; j < 30; j++) {
        wsRef.current?.send(JSON.stringify({
          event: 'media',
          streamSid: streamSidRef.current,
          media: { payload: silenceB64 }
        }))
        await new Promise(r => setTimeout(r, 10))
      }
      setStatusText('Anand is thinking...')
    } catch (err) {
      console.error(err)
      setStatusText('Speech generation error')
    } finally {
      setIsSimulatingSpeech(false)
    }
  }

  const handleCustomSpeech = (e: React.FormEvent) => {
    e.preventDefault()
    if (customText.trim()) {
      simulateSpeech(customText.trim())
      setCustomText('')
    }
  }

  const cleanUpCall = () => {
    setIsConnected(false)
    setIsAiSpeaking(false)
    setIsPttActive(false)
    setVuPercent(0)
    clearInterval(callTimerRef.current)

    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ event: 'stop', streamSid: streamSidRef.current }))
        wsRef.current.close()
      } catch {}
      wsRef.current = null
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop())
      mediaStreamRef.current = null
    }

    if (scriptNodeRef.current) {
      try { scriptNodeRef.current.disconnect() } catch {}
      scriptNodeRef.current = null
    }
  }

  const endCall = () => {
    cleanUpCall()
    setStatusText('Call ended')
  }

  const formatTimer = (totalSec: number) => {
    const mins = String(Math.floor(totalSec / 60)).padStart(2, '0')
    const secs = String(totalSec % 60).padStart(2, '0')
    return `${mins}:${secs}`
  }

  return (
    <div className="flex flex-col h-full bg-[#0b141a] text-slate-100 p-3.5 overflow-y-auto select-none space-y-2">
      
      {/* Central Agent Profile Avatar */}
      <div className="flex flex-col items-center justify-center pt-1 pb-1">
        <div className="relative w-20 h-20 mb-2">
          {/* Subtle glow / wave ring */}
          {isAiSpeaking && (
            <div className="absolute -inset-2 rounded-full bg-sky-400/35 animate-ping" />
          )}
          {isConnected && (
            <div className={`absolute -inset-1.5 rounded-full transition-all duration-300 ${
              isAiSpeaking 
                ? 'bg-sky-400/50 shadow-lg shadow-sky-500/50' 
                : 'bg-emerald-500/30 ring-2 ring-emerald-400/40 animate-pulse'
            }`} />
          )}
          <div className="relative w-full h-full rounded-full bg-gradient-to-tr from-emerald-600 via-teal-600 to-cyan-700 flex items-center justify-center text-4xl shadow-xl border-2 border-white/20 select-none overflow-hidden leading-none">
            👨‍💼
          </div>
        </div>

        <h3 className="font-extrabold text-base tracking-tight text-white">Anand Kumar</h3>
        <p className="text-xs text-slate-400 font-medium">Associative Technologies</p>

        {/* Live Call Status Pill */}
        <div className="mt-1.5 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs font-semibold shadow-xs">
          <span className={`h-2 w-2 rounded-full ${
            isConnected 
              ? (isAiSpeaking ? 'bg-sky-400 animate-pulse' : 'bg-emerald-400 animate-pulse') 
              : 'bg-slate-500'
          }`} />
          <span className={isAiSpeaking ? 'text-sky-300' : isConnected ? 'text-emerald-300' : 'text-slate-400'}>
            {isConnected ? `${statusText} (${formatTimer(callSeconds)})` : statusText}
          </span>
        </div>
      </div>

      {/* Mode Selector Pill Bar */}
      <div className="flex bg-slate-800/80 p-1 rounded-xl gap-1 border border-slate-700/60 shadow-xs">
        <button
          type="button"
          onClick={() => setCurrentMode('ptt')}
          className={`flex-1 py-1 px-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
            currentMode === 'ptt'
              ? 'bg-slate-900 text-sky-400 border border-sky-400/30 shadow-xs'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Mic className="h-3 w-3" />
          <span>Push-to-Talk</span>
        </button>
        <button
          type="button"
          onClick={() => setCurrentMode('hands-free')}
          className={`flex-1 py-1 px-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
            currentMode === 'hands-free'
              ? 'bg-slate-900 text-sky-400 border border-sky-400/30 shadow-xs'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Volume2 className="h-3 w-3" />
          <span>Hands-Free</span>
        </button>
      </div>

      {/* Live VU Meter */}
      <div className="my-1.5 space-y-1">
        <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium">
          <span>{isMuted ? 'Mic Muted' : 'Mic Input Level'}</span>
          <span>{vuPercent}%</span>
        </div>
        <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-emerald-500 via-yellow-400 to-red-500 transition-all duration-75 rounded-full"
            style={{ width: `${vuPercent}%` }}
          />
        </div>
      </div>

      {/* Main Action Bar */}
      <div className="flex items-center gap-2 my-2">
        {!isConnected ? (
          <button
            type="button"
            onClick={startCall}
            className="flex-1 py-2.5 bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-600 hover:to-green-700 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-md transition-all active:scale-98"
          >
            <Phone className="h-4 w-4" />
            <span>Call Anand Kumar</span>
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={endCall}
              className="py-2.5 px-3 bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-md transition-all shrink-0 active:scale-98"
              title="Hang Up"
            >
              <PhoneOff className="h-4 w-4" />
            </button>

            {currentMode === 'ptt' ? (
              <button
                type="button"
                onMouseDown={triggerPttStart}
                onMouseUp={triggerPttStop}
                onTouchStart={(e) => { e.preventDefault(); triggerPttStart() }}
                onTouchEnd={triggerPttStop}
                className={`flex-1 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all select-none active:scale-98 ${
                  isPttActive 
                    ? 'bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/50 scale-98' 
                    : 'bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/40'
                }`}
              >
                <Mic className="h-4 w-4" />
                <span>{isPttActive ? 'LISTENING... RELEASE TO SEND' : 'HOLD TO SPEAK (Space)'}</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={toggleMute}
                className={`flex-1 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all border ${
                  isMuted 
                    ? 'bg-red-500/20 text-red-400 border-red-500/40' 
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700'
                }`}
              >
                {isMuted ? <MicOff className="h-4 w-4 text-red-400" /> : <Mic className="h-4 w-4 text-emerald-400" />}
                <span>{isMuted ? 'Unmute Mic' : 'Mute Mic'}</span>
              </button>
            )}

            {isAiSpeaking && (
              <button
                type="button"
                onClick={sendManualInterrupt}
                className="py-2.5 px-3 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 transition-all shrink-0"
                title="Stop Anand Speaking"
              >
                <Square className="h-3.5 w-3.5 fill-amber-300" />
                <span>Stop</span>
              </button>
            )}
          </>
        )}
      </div>

      {/* Live Turn-by-Turn Transcript Box */}
      <div className="flex-1 bg-slate-950/80 border border-slate-800 rounded-xl p-2.5 my-1.5 overflow-y-auto space-y-2 text-xs max-h-44 min-h-28">
        {transcripts.map((t) => (
          <div
            key={t.id}
            className={`flex flex-col ${t.speaker === 'Caller' ? 'items-end' : 'items-start'}`}
          >
            <div className={`max-w-[85%] rounded-lg p-2 leading-relaxed ${
              t.speaker === 'Caller'
                ? 'bg-emerald-700/80 text-emerald-50 rounded-tr-none'
                : 'bg-slate-800 text-slate-100 rounded-tl-none border-l-2 border-emerald-400'
            }`}>
              <div className="font-semibold text-[10px] opacity-75 mb-0.5">
                {t.speaker}:
              </div>
              <p>{t.text}</p>
            </div>
            <span className="text-[9px] text-slate-500 mt-0.5">{t.time}</span>
          </div>
        ))}
        <div ref={transcriptEndRef} />
      </div>

      {/* Simulate Speech Quick Buttons */}
      <div className="mt-2 space-y-1.5">
        <div className="flex items-center gap-1 text-[10px] text-slate-400 font-bold uppercase tracking-wider">
          <Sparkles className="h-3 w-3 text-emerald-400" />
          <span>Quick Inbound Voice Scenarios:</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            disabled={isSimulatingSpeech}
            onClick={() => simulateSpeech('Hello Anand, what services does Associative offer?')}
            className="p-1.5 text-left bg-slate-800/70 hover:bg-slate-700/80 border border-slate-700/60 rounded-lg text-[11px] text-slate-300 hover:text-white transition-colors truncate"
          >
            💼 Services inquiry
          </button>
          <button
            type="button"
            disabled={isSimulatingSpeech}
            onClick={() => simulateSpeech('Hi Anand, I am a developer looking for a job at Associative.')}
            className="p-1.5 text-left bg-slate-800/70 hover:bg-slate-700/80 border border-slate-700/60 rounded-lg text-[11px] text-slate-300 hover:text-white transition-colors truncate"
          >
            🧑‍💻 Job inquiry
          </button>
          <button
            type="button"
            disabled={isSimulatingSpeech}
            onClick={() => simulateSpeech('Can you help me schedule a technical project discovery consultation?')}
            className="p-1.5 text-left bg-slate-800/70 hover:bg-slate-700/80 border border-slate-700/60 rounded-lg text-[11px] text-slate-300 hover:text-white transition-colors truncate"
          >
            📅 Book consultation
          </button>
          <button
            type="button"
            disabled={isSimulatingSpeech}
            onClick={() => simulateSpeech('I want to speak with a human manager right now, I am very frustrated!')}
            className="p-1.5 text-left bg-red-950/40 hover:bg-red-900/50 border border-red-800/40 rounded-lg text-[11px] text-red-300 hover:text-red-100 transition-colors truncate"
          >
            😠 Escalation test
          </button>
        </div>

        {/* Custom text-to-speech simulation row */}
        <form onSubmit={handleCustomSpeech} className="flex gap-1.5 pt-1">
          <input
            type="text"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="Type custom voice speech..."
            disabled={isSimulatingSpeech}
            className="flex-1 bg-slate-900/90 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <button
            type="submit"
            disabled={isSimulatingSpeech || !customText.trim()}
            className="px-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center shadow-xs"
          >
            <Send className="h-3 w-3" />
          </button>
        </form>
      </div>

    </div>
  )
}
