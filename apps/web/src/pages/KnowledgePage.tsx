import { useState } from 'react'
import { Upload, Link as LinkIcon, FileText, Database, Loader2, Trash2 } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { apiClient } from '../services/api'

export default function KnowledgePage() {
  const { workspace } = useAuthStore()
  const [activeTab, setActiveTab] = useState<'upload' | 'url'>('upload')
  const [loading, setLoading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !workspace?.id) return

    setLoading(true)
    setMessage(null)
    const formData = new FormData()
    formData.append('file', file)

    try {
      await apiClient.post(`/knowledge/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'X-Workspace-ID': workspace.id
        }
      })
      setMessage({ type: 'success', text: 'Document uploaded and is being processed by the AI.' })
      setFile(null)
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.message || 'Failed to upload document.' })
    } finally {
      setLoading(false)
    }
  }

  const handleUrlUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url || !workspace?.id) return

    setLoading(true)
    setMessage(null)

    try {
      await apiClient.post(`/knowledge/url`, { url }, {
        headers: { 'X-Workspace-ID': workspace.id }
      })
      setMessage({ type: 'success', text: 'URL submitted. The AI is crawling the content.' })
      setUrl('')
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.message || 'Failed to process URL.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Database className="h-6 w-6 text-primary" />
            Knowledge Base
          </h1>
          <p className="text-muted-foreground mt-1">Upload documents and URLs to teach your AI agent.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Ingestion Panel */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            <div className="flex border-b border-border">
              <button
                className={`flex-1 py-3 px-4 text-sm font-medium flex items-center justify-center gap-2 ${activeTab === 'upload' ? 'bg-primary/10 text-primary border-b-2 border-primary' : 'text-muted-foreground hover:bg-secondary'}`}
                onClick={() => setActiveTab('upload')}
              >
                <Upload className="h-4 w-4" />
                Upload PDF/Doc
              </button>
              <button
                className={`flex-1 py-3 px-4 text-sm font-medium flex items-center justify-center gap-2 ${activeTab === 'url' ? 'bg-primary/10 text-primary border-b-2 border-primary' : 'text-muted-foreground hover:bg-secondary'}`}
                onClick={() => setActiveTab('url')}
              >
                <LinkIcon className="h-4 w-4" />
                Add URL
              </button>
            </div>

            <div className="p-6">
              {message && (
                <div className={`p-4 rounded-md mb-6 ${message.type === 'success' ? 'bg-whatsapp/10 text-whatsapp border border-whatsapp/20' : 'bg-destructive/10 text-destructive border border-destructive/20'}`}>
                  {message.text}
                </div>
              )}

              {activeTab === 'upload' ? (
                <form onSubmit={handleFileUpload} className="space-y-4">
                  <div className="border-2 border-dashed border-border rounded-xl p-10 flex flex-col items-center justify-center bg-secondary/30 text-center hover:bg-secondary/50 transition-colors cursor-pointer relative">
                    <input 
                      type="file" 
                      accept=".pdf,.txt,.docx"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                    <FileText className="h-10 w-10 text-muted-foreground mb-3" />
                    <p className="text-sm font-medium">{file ? file.name : 'Click or drag file to this area to upload'}</p>
                    <p className="text-xs text-muted-foreground mt-1">Supports PDF, TXT, DOCX (Max 10MB)</p>
                  </div>
                  <button 
                    type="submit" 
                    disabled={!file || loading}
                    className="w-full bg-primary hover:bg-primary/90 text-primary-foreground py-2 rounded-md font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                    {loading ? 'Processing...' : 'Upload Document'}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleUrlUpload} className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Website URL</label>
                    <input
                      type="url"
                      required
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      placeholder="https://example.com/pricing"
                      className="w-full p-3 rounded-md border border-input bg-background focus:ring-2 focus:ring-primary/50 outline-none"
                    />
                    <p className="text-xs text-muted-foreground">The AI will scrape this page and add its contents to your knowledge base.</p>
                  </div>
                  <button 
                    type="submit" 
                    disabled={!url || loading}
                    className="w-full bg-primary hover:bg-primary/90 text-primary-foreground py-2 rounded-md font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <LinkIcon className="h-4 w-4" />}
                    {loading ? 'Crawling...' : 'Add Source'}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>

        {/* Existing Sources Panel */}
        <div className="bg-card border border-border rounded-xl shadow-sm p-6 flex flex-col h-full">
          <h2 className="text-lg font-bold border-b border-border pb-3 mb-4 flex items-center justify-between">
            Trained Sources
            <span className="bg-primary/10 text-primary text-xs px-2 py-1 rounded-full font-medium">0 active</span>
          </h2>
          
          <div className="flex-1 flex flex-col items-center justify-center text-center text-muted-foreground py-10">
            <Database className="h-12 w-12 mb-3 opacity-20" />
            <p className="text-sm">No knowledge sources yet.</p>
            <p className="text-xs mt-1">Upload a file or add a URL to train your AI.</p>
          </div>
          
          {/* Example of a source row (hidden for now) */}
          {/* <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg border border-border">
              <div className="flex items-center gap-3 overflow-hidden">
                <FileText className="h-4 w-4 text-primary shrink-0" />
                <div className="truncate">
                  <p className="text-sm font-medium truncate">Product_Catalog.pdf</p>
                  <p className="text-xs text-muted-foreground">Processed today • 45 chunks</p>
                </div>
              </div>
              <button className="text-muted-foreground hover:text-destructive p-1 transition-colors">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div> */}
        </div>

      </div>
    </div>
  )
}
