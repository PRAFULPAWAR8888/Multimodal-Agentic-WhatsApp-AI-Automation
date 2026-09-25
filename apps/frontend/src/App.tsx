import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { MessageSquare, Settings, Users, Activity, LogOut } from 'lucide-react';
import ConversationsList from './components/ConversationsList';
import ConversationDetail from './components/ConversationDetail';

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6">
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary-600 to-indigo-600">
            WhatsApp AI
          </h1>
          <p className="text-xs text-gray-500 mt-1">Multimodal Automation</p>
        </div>
        
        <nav className="flex-1 px-4 space-y-1">
          <Link to="/" className="flex items-center gap-3 px-3 py-2.5 bg-primary-50 text-primary-700 rounded-lg font-medium transition-colors">
            <MessageSquare className="w-5 h-5" />
            Conversations
          </Link>
          <Link to="/analytics" className="flex items-center gap-3 px-3 py-2.5 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">
            <Activity className="w-5 h-5" />
            Analytics
          </Link>
          <Link to="/agents" className="flex items-center gap-3 px-3 py-2.5 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">
            <Users className="w-5 h-5" />
            Agents
          </Link>
          <Link to="/settings" className="flex items-center gap-3 px-3 py-2.5 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">
            <Settings className="w-5 h-5" />
            Settings
          </Link>
        </nav>
        
        <div className="p-4 border-t border-gray-200">
          <button className="flex items-center gap-3 px-3 py-2 text-gray-600 hover:text-danger-600 transition-colors w-full">
            <LogOut className="w-5 h-5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {children}
      </main>
    </div>
  );
}

function Inbox() {
  return (
    <div className="flex h-full w-full">
      <ConversationsList />
      <Routes>
        <Route path="/" element={
          <div className="flex-1 flex flex-col items-center justify-center bg-white/50 text-gray-400">
            <MessageSquare className="w-16 h-16 mb-4 text-gray-300" />
            <p>Select a conversation to view</p>
          </div>
        } />
        <Route path="/:id" element={<ConversationDetail />} />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/*" element={<Inbox />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}

export default App;
