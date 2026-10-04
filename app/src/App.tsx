import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Layout } from "@/components/Layout"
import LandingPage from "@/pages/LandingPage"
import LibraryPage from "@/pages/LibraryPage"
import BuilderPage from "@/pages/BuilderPage"
import ResultsPage from "@/pages/ResultsPage"
import ScaffoldDetailPage from "@/pages/ScaffoldDetailPage"

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/builder" element={<BuilderPage />} />
          <Route path="/results/:id" element={<ResultsPage />} />
          <Route path="/library/scaffold/:id" element={<ScaffoldDetailPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
