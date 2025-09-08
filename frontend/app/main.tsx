import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { DashboardPage } from './components/DashboardPage'
import { PWAInstallPrompt } from './components/PWAInstallPrompt'
import { PWAUpdatePrompt } from './components/PWAUpdatePrompt'
import './index.css'

function App() {
  const [showUpdatePrompt, setShowUpdatePrompt] = useState(false)

  // PWA Update functionality
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js')
        .then((registration) => {
          console.log('SW registered: ', registration)
        })
        .catch((registrationError) => {
          console.log('SW registration failed: ', registrationError)
        })

      navigator.serviceWorker.addEventListener('controllerchange', () => {
        setShowUpdatePrompt(true)
      })
    }
  }, [])

  const handlePWAUpdate = () => {
    setShowUpdatePrompt(false)
    window.location.reload()
  }

  return (
    <div className="min-h-screen bg-gray-50 flex w-full">
      <div className="flex-1 w-full">
        <DashboardPage />
      </div>

      {/* PWA Components */}
      <PWAInstallPrompt />
      <PWAUpdatePrompt show={showUpdatePrompt} onUpdate={handlePWAUpdate} />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)