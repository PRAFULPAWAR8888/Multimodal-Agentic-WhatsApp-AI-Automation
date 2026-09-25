import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useStore } from '../store/useStore';
import clsx from 'clsx';
import { Send, Bot, User, Mic } from 'lucide-react';

export default function ConversationDetail() {
  const { id } = useParams();
  const { conversations, messages, fetchMessages, sendMessage } = useStore();
  const [text, setText] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  const conv = conversations.find(c => c.id === id);

  useEffect(() => {
    if (id) {
      fetchMessages(id);
      const interval = setInterval(() => fetchMessages(id), 5000);
      return () => clearInterval(interval);
    }
  }, [id, fetchMessages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!conv) return null;

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !id) return;
    sendMessage(id, text);
    setText('');
  };

  return (
    <div className="flex-1 flex flex-col bg-white h-full relative">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-white/80 backdrop-blur-md sticky top-0 z-10">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">{conv.contact_name}</h2>
          <p className="text-sm text-gray-500">{conv.contact_phone}</p>
        </div>
        <div>
           {conv.status === 'ESCALATED' ? (
             <div className="px-3 py-1 bg-danger-100 text-danger-700 font-medium rounded-full text-sm animate-pulse">
               Needs Human Attention
             </div>
           ) : conv.ai_enabled ? (
             <div className="flex items-center gap-1.5 px-3 py-1 bg-primary-100 text-primary-700 font-medium rounded-full text-sm">
               <Bot className="w-4 h-4" /> AI Handling
             </div>
           ) : (
             <div className="flex items-center gap-1.5 px-3 py-1 bg-gray-100 text-gray-700 font-medium rounded-full text-sm">
               <User className="w-4 h-4" /> Human Mode
             </div>
           )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50">
        {messages.map((msg) => {
          const isOutbound = msg.direction === 'OUTBOUND';
          return (
            <div key={msg.id} className={clsx("flex flex-col max-w-[75%]", isOutbound ? "ml-auto items-end" : "mr-auto items-start")}>
              <div 
                className={clsx(
                  "px-4 py-2.5 rounded-2xl shadow-sm",
                  isOutbound 
                    ? "bg-primary-600 text-white rounded-br-none" 
                    : "bg-white border border-gray-200 text-gray-800 rounded-bl-none"
                )}
              >
                {msg.is_voice_note && (
                  <div className="flex items-center gap-2 mb-1 opacity-80 text-sm font-medium">
                    <Mic className="w-4 h-4" />
                    <span>Voice Note Transcription</span>
                  </div>
                )}
                <p className="whitespace-pre-wrap">{msg.body}</p>
              </div>
              <span className="text-[11px] text-gray-400 mt-1 px-1">
                {new Date(msg.timestamp + 'Z').toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} • {msg.status}
              </span>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="p-4 bg-white border-t border-gray-200">
        <form onSubmit={handleSend} className="flex items-center gap-3">
          <input 
            type="text" 
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={conv.ai_enabled ? "AI is handling this... (Send a message to takeover)" : "Type your reply..."}
            className="flex-1 bg-gray-100 border-transparent focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-200 rounded-full px-5 py-3 transition-all outline-none text-gray-700"
          />
          <button 
            type="submit"
            disabled={!text.trim()}
            className="p-3 bg-primary-600 text-white rounded-full hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
}
