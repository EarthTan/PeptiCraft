import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Layout } from "@/components/Layout"
import LandingPage from "@/pages/LandingPage"
import LibraryPage from "@/pages/LibraryPage"
import BuilderPage from "@/pages/BuilderPage"
import ResultsPage from "@/pages/ResultsPage"
import ScaffoldDetailPage from "@/pages/ScaffoldDetailPage"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"

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
          <Route
            path="*"
            element={
              <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center">
                <p className="text-sm font-semibold uppercase tracking-widest text-primary-600">
                  Page not found
                </p>
                <h1 className="mt-3 text-3xl sm:text-4xl font-bold text-primary-900">
                  This page is not in the PeptiCraft library.
                </h1>
                <p className="mt-4 text-primary-600">
                  The link may be incomplete or the page may have moved. Continue to the project
                  overview or open the candidate library.
                </p>
                <div className="mt-8 flex flex-col sm:flex-row justify-center gap-3">
                  <Link to="/">
                    <Button variant="gradient">Back to overview</Button>
                  </Link>
                  <Link to="/library">
                    <Button variant="outline">Browse the library</Button>
                  </Link>
                </div>
              </section>
            }
          />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
