import SmartHomeScene from './components/SmartHomeScene.jsx'
import SecurityDashboard from './components/SecurityDashboard.jsx'
import Sidebar from './components/Sidebar.jsx'
import AlertPanel from './components/AlertPanel.jsx'
import DeviceInspector from './components/DeviceInspector.jsx'
import { useSecurityFeed } from './lib/useSecurityFeed.js'
import './styles/dashboard.css'

export default function App() {
  useSecurityFeed()

  return (
    <div className="app">
      <SecurityDashboard />
      <Sidebar />
      <SmartHomeScene />
      <DeviceInspector />
      <AlertPanel />
    </div>
  )
}
