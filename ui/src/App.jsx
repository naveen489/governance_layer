import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import Header from './components/Header.jsx'
import Dashboard from './pages/Dashboard.jsx'
import ReviewQueue from './pages/ReviewQueue.jsx'
import Assets from './pages/Assets.jsx'
import Policies from './pages/Policies.jsx'
import Exceptions from './pages/Exceptions.jsx'
import Audit from './pages/Audit.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <div className="main-content">
          <Header />
          <div className="page-body">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/reviews" element={<ReviewQueue />} />
              <Route path="/assets" element={<Assets />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/exceptions" element={<Exceptions />} />
              <Route path="/audit" element={<Audit />} />
            </Routes>
          </div>
        </div>
      </div>
    </BrowserRouter>
  )
}
