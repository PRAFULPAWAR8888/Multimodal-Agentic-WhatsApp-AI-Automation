import { useState, useRef, useEffect } from 'react'
import { 
  Send, Mic, Bot, Loader2, Sparkles, 
  Paperclip, X, FileText, Trash2, Volume2,
  Phone, PhoneCall, MessageSquare, ArrowLeft 
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { apiClient } from '../services/api'
import VoiceCallSimulator from '../components/VoiceCallSimulator'

type Attachment = {
  file: File
  name: string
  size: number
  type: string
  previewUrl?: string
  dataUrl: string
  isImage: boolean
  isPdf: boolean
}

type Message = {
  id: string
  text: string
  sender: 'user' | 'ai'
  timestamp: Date
  modality?: 'text' | 'image' | 'document' | 'voice'
  attachment?: {
    name: string
    size?: number
    previewUrl?: string
    isImage?: boolean
    isPdf?: boolean
  }
  voice?: {
    audioUrl?: string
    duration?: number
  }
  metadata?: {
    intent?: string
    latency_ms?: number
    routed_agent?: string
  }
}

export default function PlaygroundPage() {
  const { workspace } = useAuthStore()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [attachment, setAttachment] = useState<Attachment | null>(null)
  const [activeTab, setActiveTab] = useState<'chat' | 'call'>('chat')
  
  // Voice recording states
  const [isRecording, setIsRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [liveTranscript, setLiveTranscript] = useState('')
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const recordingTimerRef = useRef<any>(null)
  const recognitionRef = useRef<any>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Clean up any recording on unmount
  useEffect(() => {
    return () => {
      clearInterval(recordingTimerRef.current)
      if (recognitionRef.current) {
        try { recognitionRef.current.stop() } catch {}
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
        mediaRecorderRef.current.stream.getTracks().forEach(t => t.stop())
      }
    }
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const isImage = file.type.startsWith('image/')
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result as string
      setAttachment({
        file,
        name: file.name,
        size: file.size,
        type: file.type || (isPdf ? 'application/pdf' : 'application/octet-stream'),
        previewUrl: isImage ? dataUrl : undefined,
        dataUrl,
        isImage,
        isPdf
      })
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []
      setLiveTranscript('')

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.start()
      setIsRecording(true)
      setRecordingSeconds(0)

      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds(prev => prev + 1)
      }, 1000)

      // Optional real-time speech recognition
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      if (SpeechRecognition) {
        try {
          const rec = new SpeechRecognition()
          rec.continuous = true
          rec.interimResults = true
          rec.lang = 'en-US'
          rec.onresult = (event: any) => {
            let tr = ''
            for (let i = 0; i < event.results.length; i++) {
              tr += event.results[i][0].transcript
            }
            if (tr) setLiveTranscript(tr)
          }
          rec.start()
          recognitionRef.current = rec
        } catch (e) {
          console.warn('Speech recognition not started:', e)
        }
      }
    } catch (err) {
      console.error('Microphone error:', err)
      alert('Could not access microphone. Please allow microphone access in your browser.')
    }
  }

  const stopRecording = (shouldSend = true) => {
    if (!mediaRecorderRef.current) return

    clearInterval(recordingTimerRef.current)
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
    }

    const duration = recordingSeconds
    const capturedTranscript = liveTranscript

    mediaRecorderRef.current.onstop = () => {
      mediaRecorderRef.current?.stream.getTracks().forEach(track => track.stop())
      setIsRecording(false)
      setRecordingSeconds(0)

      if (shouldSend) {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const audioUrl = URL.createObjectURL(audioBlob)

        const reader = new FileReader()
        reader.onloadend = () => {
          const base64Audio = reader.result as string
          sendVoiceMessage(capturedTranscript || 'Voice message', base64Audio, audioUrl, duration)
        }
        reader.readAsDataURL(audioBlob)
      }
    }

    mediaRecorderRef.current.stop()
  }

  const cancelRecording = () => {
    stopRecording(false)
    setLiveTranscript('')
  }

  const sendVoiceMessage = async (
    transcript: string,
    base64Audio: string,
    audioUrl: string,
    duration: number
  ) => {
    if (loading) return
    const userMessage: Message = {
      id: Date.now().toString(),
      text: transcript,
      sender: 'user',
      timestamp: new Date(),
      modality: 'voice',
      voice: { audioUrl, duration }
    }

    setMessages(prev => [...prev, userMessage])
    setLoading(true)
    setLiveTranscript('')

    try {
      const wsId = workspace?.id || 'default'
      const response = await apiClient.post(`/workspaces/${wsId}/playground/chat`, {
        message: transcript,
        modality: 'voice',
        file_data: base64Audio,
        file_name: 'voice_note.webm',
        file_type: 'audio/webm',
        sender_id: 'playground_user'
      })

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.data.response_text || response.data.response || 'No response',
        sender: 'ai',
        timestamp: new Date(),
        metadata: {
          intent: response.data.intent,
          latency_ms: response.data.latency_ms,
          routed_agent: response.data.routed_agent
        }
      }
      setMessages(prev => [...prev, aiMessage])
    } catch (err: any) {
      const errorMsg = err.response?.data?.message || err.response?.data?.detail || 'Failed to get response'
      const details = err.response?.data?.details?.map((d: any) => d.message).join(', ')
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        text: `Error: ${errorMsg}${details ? ` (${details})` : ''}`,
        sender: 'ai',
        timestamp: new Date()
      }])
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async (textToSend: string) => {
    if ((!textToSend.trim() && !attachment) || loading) return

    const currentAttachment = attachment
    const userMessage: Message = {
      id: Date.now().toString(),
      text: textToSend.trim() || (currentAttachment ? (currentAttachment.isImage ? 'Sent an image' : `Sent ${currentAttachment.name}`) : ''),
      sender: 'user',
      timestamp: new Date(),
      modality: currentAttachment ? (currentAttachment.isImage ? 'image' : 'document') : 'text',
      attachment: currentAttachment ? {
        name: currentAttachment.name,
        size: currentAttachment.size,
        previewUrl: currentAttachment.previewUrl,
        isImage: currentAttachment.isImage,
        isPdf: currentAttachment.isPdf
      } : undefined
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setAttachment(null)
    setLoading(true)

    try {
      const wsId = workspace?.id || 'default'
      const payload: any = {
        message: textToSend.trim(),
        sender_id: 'playground_user'
      }

      if (currentAttachment) {
        payload.modality = currentAttachment.isImage ? 'image' : 'document'
        payload.file_name = currentAttachment.name
        payload.file_type = currentAttachment.type
        payload.file_data = currentAttachment.dataUrl
      }

      const response = await apiClient.post(`/workspaces/${wsId}/playground/chat`, payload)

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.data.response_text || response.data.response || 'No response',
        sender: 'ai',
        timestamp: new Date(),
        metadata: {
          intent: response.data.intent,
          latency_ms: response.data.latency_ms,
          routed_agent: response.data.routed_agent
        }
      }
      setMessages(prev => [...prev, aiMessage])
    } catch (err: any) {
      const errorMsg = err.response?.data?.message || err.response?.data?.detail || 'Failed to get response'
      const details = err.response?.data?.details?.map((d: any) => d.message).join(', ')
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        text: `Error: ${errorMsg}${details ? ` (${details})` : ''}`,
        sender: 'ai',
        timestamp: new Date()
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  const formatDuration = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return ''
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] max-w-6xl mx-auto gap-6 lg:flex-row">
      
      {/* Phone Simulator Container */}
      <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-900 border border-border rounded-3xl overflow-hidden shadow-2xl relative max-w-md mx-auto w-full">
        {/* Phone Header */}
        {activeTab === 'call' ? (
          <div className="bg-[#111b21] text-white px-4 py-3 flex items-center justify-between border-b border-white/10 shadow-sm z-10">
            <button
              type="button"
              onClick={() => setActiveTab('chat')}
              className="flex items-center gap-1.5 text-xs text-white/80 hover:text-white transition-colors bg-white/10 hover:bg-white/15 px-2.5 py-1.5 rounded-lg active:scale-95"
              title="Return to WhatsApp Chat"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to Chat</span>
            </button>

            <div className="text-center">
              <span className="text-[11px] font-bold text-emerald-400 flex items-center justify-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Live Telephony Line
              </span>
              <span className="text-[10px] text-white/50 block font-mono">8kHz &mu;-Law Live</span>
            </div>

            <div className="flex items-center bg-white/10 p-0.5 rounded-lg text-xs">
              <button
                type="button"
                onClick={() => setActiveTab('chat')}
                className="px-2 py-1 rounded text-white/70 hover:text-white transition-all text-[11px]"
              >
                Chat
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded bg-emerald-500 text-slate-950 font-bold text-[11px] shadow-xs"
              >
                Call
              </button>
            </div>
          </div>
        ) : (
          <div className="bg-whatsapp text-white p-3.5 flex items-center justify-between shadow-md z-10">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-white/20 rounded-full flex items-center justify-center">
                <Bot className="h-6 w-6" />
              </div>
              <div>
                <h2 className="font-bold text-sm leading-tight">AI Assistant</h2>
                <p className="text-[11px] text-white/80 flex items-center gap-1">
                  <span className="h-2 w-2 bg-green-300 rounded-full inline-block"></span>
                  Online • Multimodal AI
                </p>
              </div>
            </div>

            {/* Mode Switcher Buttons */}
            <div className="flex items-center bg-black/20 p-1 rounded-xl gap-1">
              <button
                type="button"
                className="px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 bg-white text-whatsapp shadow-xs"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                <span>Chat</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('call')}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 text-white/80 hover:text-white transition-all"
                title="Switch to AI Voice Call"
              >
                <Phone className="h-3.5 w-3.5" />
                <span>Voice Call</span>
              </button>
            </div>
          </div>
        )}

        {activeTab === 'call' ? (
          <div className="flex-1 flex flex-col overflow-hidden bg-[#0b141a]">
            <VoiceCallSimulator
              onCallTranscript={(role, text) => {
                const callMessage: Message = {
                  id: Date.now().toString() + Math.random().toString().slice(2, 6),
                  text: text,
                  sender: role,
                  timestamp: new Date(),
                  modality: 'voice',
                  metadata: {
                    intent: 'telephony_voice_call',
                    routed_agent: 'anand_kumar_voice_agent'
                  }
                }
                setMessages(prev => [...prev, callMessage])
              }}
            />
          </div>
        ) : (
          <>
            {/* Chat Area (WhatsApp Background) */}
            <div 
              className="flex-1 overflow-y-auto p-4 space-y-4 bg-[url('https://static.whatsapp.net/rsrc.php/v3/yl/r/r2_yqN1G6Xh.png')] bg-repeat"
              style={{ backgroundColor: '#efeae2' }}
            >
              {messages.length === 0 && (
                <div className="bg-[#ffeecd] text-[#54656f] text-xs p-3 rounded-lg text-center mx-auto max-w-[85%] shadow-sm mb-4">
                  <Sparkles className="h-3.5 w-3.5 inline mr-1 text-amber-600" />
                  Chat is secured with Multimodal AI. You can send text, attach images or PDFs, or click <strong>Voice Call</strong> above to speak live!
                </div>
              )}

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <div 
                    className={`max-w-[85%] rounded-lg p-2.5 shadow-sm relative ${
                      msg.sender === 'user' 
                        ? 'bg-[#d9fdd3] text-[#111b21] rounded-tr-none' 
                        : 'bg-white text-[#111b21] rounded-tl-none'
                    }`}
                  >
                    {/* Image attachment rendering */}
                    {msg.attachment?.isImage && msg.attachment.previewUrl && (
                      <div className="mb-2">
                        <img 
                          src={msg.attachment.previewUrl} 
                          alt={msg.attachment.name}
                          className="rounded-lg max-h-56 w-full object-cover border border-black/10 shadow-sm"
                        />
                      </div>
                    )}

                    {/* PDF/Document attachment rendering */}
                    {msg.attachment && !msg.attachment.isImage && (
                      <div className="flex items-center gap-2 p-2.5 rounded-lg bg-black/5 mb-2 border border-black/10">
                        <FileText className="h-6 w-6 text-red-500 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold truncate text-[#111b21]">{msg.attachment.name}</p>
                          {msg.attachment.size && (
                            <p className="text-[10px] text-gray-500">{formatFileSize(msg.attachment.size)}</p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Voice note rendering */}
                    {msg.modality === 'voice' && (
                      <div className="mb-2 p-2 bg-emerald-50 rounded-lg border border-emerald-200">
                        <div className="flex items-center gap-2 text-xs font-medium text-emerald-800 mb-1">
                          <Volume2 className="h-4 w-4 text-emerald-600" />
                          <span>Voice Telephony Turn</span>
                        </div>
                        {msg.voice?.audioUrl && (
                          <audio controls src={msg.voice.audioUrl} className="h-8 w-full max-w-[220px]" />
                        )}
                      </div>
                    )}

                    {/* Message text */}
                    {msg.text && (
                      <p className="text-sm pb-3 whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                    )}

                    <span className="text-[10px] text-gray-500 absolute bottom-1 right-2">
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  
                  {/* Metadata badge for AI responses */}
                  {msg.metadata && (
                    <div className="mt-1 flex items-center gap-2 text-[10px] font-mono text-muted-foreground bg-card/90 px-2 py-0.5 rounded-full border border-border backdrop-blur-sm shadow-xs">
                      {msg.metadata.latency_ms && <span>{msg.metadata.latency_ms}ms •</span>}
                      <span className="text-primary font-medium">{msg.metadata.intent}</span>
                      <span>•</span>
                      <span>{msg.metadata.routed_agent}</span>
                    </div>
                  )}
                </div>
              ))}
              
              {loading && (
                <div className="flex items-start">
                  <div className="bg-white rounded-lg rounded-tl-none p-3 shadow-sm flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin text-whatsapp" />
                    <span className="text-xs italic">AI is analyzing and thinking...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Attachment Preview (if selected) */}
            {attachment && (
              <div className="bg-slate-200 px-3 py-2 flex items-center justify-between border-t border-border">
                <div className="flex items-center gap-2 min-w-0">
                  {attachment.isImage && attachment.previewUrl ? (
                    <img 
                      src={attachment.previewUrl} 
                      alt="preview" 
                      className="h-10 w-10 rounded-md object-cover border border-slate-300 shadow-sm"
                    />
                  ) : (
                    <div className="h-10 w-10 rounded-md bg-white flex items-center justify-center border border-slate-300">
                      <FileText className="h-5 w-5 text-red-500" />
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-800 truncate max-w-[220px]">
                      {attachment.name}
                    </p>
                    <p className="text-[10px] text-slate-500">
                      {formatFileSize(attachment.size)}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setAttachment(null)}
                  className="p-1.5 hover:bg-slate-300 rounded-full transition-colors text-slate-600"
                  title="Remove attachment"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            {/* Hidden File Input */}
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileSelect} 
              accept="image/*,.pdf,.doc,.docx,.txt" 
              className="hidden" 
            />

            {/* Input Area */}
            <div className="bg-slate-100 p-2.5 flex items-center gap-2 border-t border-slate-200">
              {isRecording ? (
                /* Active Voice Recording UI */
                <div className="flex-1 flex items-center justify-between bg-white py-1.5 px-3 rounded-full border border-red-200 shadow-xs">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-red-600"></span>
                    </span>
                    <span className="text-xs font-medium text-red-600">
                      {formatDuration(recordingSeconds)}
                    </span>
                    <span className="text-xs text-muted-foreground truncate max-w-[160px]">
                      {liveTranscript ? `"${liveTranscript}"` : 'Listening... Speak now'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={cancelRecording}
                      className="p-1 text-slate-400 hover:text-red-500 transition-colors"
                      title="Cancel recording"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => stopRecording(true)}
                      className="p-1.5 bg-whatsapp text-white rounded-full hover:bg-whatsapp/90 transition-colors shadow-xs"
                      title="Send voice note"
                    >
                      <Send className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ) : (
                /* Normal Input Bar */
                <>
                  {/* Attachment Button */}
                  <button 
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={loading}
                    title="Attach Image or Document"
                    className="p-2 text-gray-500 hover:text-whatsapp hover:bg-slate-200 rounded-full transition-colors"
                  >
                    <Paperclip className="h-5 w-5" />
                  </button>

                  {/* Message Input Form */}
                  <form onSubmit={handleSend} className="flex-1 flex">
                    <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder={attachment ? "Add a caption (optional)..." : "Type a message..."}
                      className="flex-1 py-2 px-4 rounded-full border border-slate-300 focus:outline-none focus:ring-1 focus:ring-whatsapp text-sm shadow-xs bg-white text-slate-800"
                      disabled={loading}
                    />
                  </form>

                  {/* Send or Mic Button */}
                  {input.trim() || attachment ? (
                    <button 
                      type="button"
                      onClick={handleSend}
                      disabled={loading}
                      className="p-2.5 bg-whatsapp text-white rounded-full hover:bg-whatsapp/90 transition-colors shadow-sm disabled:opacity-50"
                      title="Send message"
                    >
                      <Send className="h-4 w-4 ml-0.5" />
                    </button>
                  ) : (
                    <button 
                      type="button"
                      onClick={startRecording}
                      disabled={loading}
                      className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors"
                      title="Hold or click to record voice note"
                    >
                      <Mic className="h-5 w-5" />
                    </button>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>

      {/* Analytics / Side Panel */}
      <div className="flex-1 flex flex-col gap-4">
        {/* Telephony Voice Call Launch Card */}
        <div className="bg-gradient-to-br from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/30 p-5 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-emerald-400 flex items-center gap-2">
              <PhoneCall className="h-4 w-4 text-emerald-400 animate-pulse" />
              AI Voice Call Agent (Telephony)
            </h2>
            <span className="text-[10px] uppercase font-bold tracking-wider bg-emerald-500/15 text-emerald-300 px-2.5 py-0.5 rounded-full border border-emerald-500/30">
              Live FreeSWITCH / Twilio
            </span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Test natural back-and-forth telephone conversations with Anand Kumar using 8kHz &mu;-Law audio streaming, Whisper STT, GPT-4o-mini, and Piper/OpenAI voice.
          </p>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => setActiveTab('call')}
              className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition-all shadow-xs flex items-center justify-center gap-2 ${
                activeTab === 'call'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/30'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white'
              }`}
            >
              <Phone className="h-3.5 w-3.5" />
              <span>{activeTab === 'call' ? '● Voice Call Active' : 'Switch to Voice Call'}</span>
            </button>
            {activeTab === 'call' && (
              <button
                onClick={() => setActiveTab('chat')}
                className="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                <span>Return to Chat</span>
              </button>
            )}
          </div>
        </div>

        {/* Quick Test Chips */}
        <div className="bg-card border border-border p-6 rounded-xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Quick Test Prompts
            </h2>
            {messages.length > 0 && (
              <button
                onClick={() => setMessages([])}
                className="text-xs text-muted-foreground hover:text-destructive transition-colors font-medium"
              >
                Clear Chat
              </button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Click any prompt to instantly test your multi-agent routing, RAG retrieval, and CRM lead capture.
          </p>
          <div className="space-y-2 pt-1">
            {[
              { label: "💼 Inquire Services", text: "What services and software development solutions do you provide?" },
              { label: "📅 Book Consultation", text: "Can I schedule a technical discovery call tomorrow afternoon?" },
              { label: "📝 Register Lead", text: "My name is John Doe, email is john.doe@example.com, and we need algorithmic trading software." },
              { label: "👤 Human Escalation", text: "I would like to speak directly with a human team member please." }
            ].map((prompt, idx) => (
              <button
                key={idx}
                disabled={loading}
                onClick={() => {
                  setActiveTab('chat')
                  sendMessage(prompt.text)
                }}
                className="w-full text-left p-2.5 rounded-lg bg-secondary/50 hover:bg-primary/10 hover:border-primary/30 border border-border text-xs transition-colors flex items-center justify-between group disabled:opacity-50"
              >
                <div>
                  <span className="font-semibold text-foreground group-hover:text-primary block">
                    {prompt.label}
                  </span>
                  <span className="text-[11px] text-muted-foreground line-clamp-1">
                    "{prompt.text}"
                  </span>
                </div>
                <Send className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary shrink-0 ml-2" />
              </button>
            ))}
          </div>
        </div>

        {/* Live Performance Panel */}
        <div className="bg-card border border-border p-6 rounded-xl shadow-sm space-y-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <Bot className="h-5 w-5 text-whatsapp" />
            Live Agent Performance
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-secondary/30 rounded-lg border border-border">
              <span className="text-[11px] text-muted-foreground uppercase font-bold tracking-wider">Average Latency</span>
              <p className="text-xl font-bold mt-1">
                {messages.filter(m => m.metadata?.latency_ms).length > 0 
                  ? Math.round(messages.reduce((acc, m) => acc + (m.metadata?.latency_ms || 0), 0) / messages.filter(m => m.metadata?.latency_ms).length)
                  : 0} ms
              </p>
            </div>
            <div className="p-3 bg-secondary/30 rounded-lg border border-border">
              <span className="text-[11px] text-muted-foreground uppercase font-bold tracking-wider">Session Messages</span>
              <p className="text-xl font-bold mt-1">{messages.length}</p>
            </div>
          </div>
          <div className="space-y-2">
            <div className="p-2.5 bg-whatsapp/10 border border-whatsapp/20 rounded-lg flex items-center justify-between text-xs text-whatsapp font-medium">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-whatsapp animate-pulse"></span>
                <span>LangGraph Multi-Agent Engine Active</span>
              </div>
              <span className="text-[10px] font-mono text-muted-foreground">GPT-4o-mini</span>
            </div>
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center justify-between text-xs text-emerald-400 font-medium">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Bi-Directional Telephony Streaming</span>
              </div>
              <span className="text-[10px] font-mono text-emerald-300">8kHz &mu;-Law</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
