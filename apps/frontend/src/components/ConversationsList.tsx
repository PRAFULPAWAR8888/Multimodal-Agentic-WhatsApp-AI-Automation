import { useEffect } from 'react';
import { useStore } from '../store/useStore';
import { useNavigate, useParams } from 'react-router-dom';
import clsx from 'clsx';
import { Bot, User, AlertCircle } from 'lucide-react';

export default function ConversationsList() {
  const { conversations, fetchConversations } = useStore();
  const navigate = useNavigate();
  const { id } = useParams();

  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 5000);
    return () => clearInterval(interval);
  }, [fetchConversations]);

  return (
    <div className="w-80 bg-white border-r border-gray-200 flex flex-col h-full">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800">Inbox</h2>
      </div>
      <div className="overflow-y-auto flex-1">
        {conversations.map((conv) => (
          <div 
            key={conv.id}
            onClick={() => navigate(`/${conv.id}`)}
            className={clsx(
              "p-4 border-b border-gray-100 cursor-pointer transition-colors hover:bg-gray-50",
              id === conv.id ? "bg-primary-50" : ""
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-gray-900 truncate">
                {conv.contact_name}
              </span>
              <span className="text-xs text-gray-500">
                {conv.last_message_at ? new Date(conv.last_message_at + 'Z').toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}
              </span>
            </div>
            <div className="text-sm text-gray-500 mb-2 truncate">
              {conv.contact_phone}
            </div>
            <div className="flex items-center gap-2">
              {conv.status === 'ESCALATED' && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-danger-100 text-danger-700">
                  <AlertCircle className="w-3 h-3" /> Escalated
                </span>
              )}
              {conv.ai_enabled ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-700">
                  <Bot className="w-3 h-3" /> AI Active
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                  <User className="w-3 h-3" /> Human Mode
                </span>
              )}
            </div>
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="p-8 text-center text-gray-500 text-sm">
            No conversations yet.
          </div>
        )}
      </div>
    </div>
  );
}
