import { useState, useEffect } from "react"
import { Link, useLocation } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { DataSourceBanner } from "@/components/DataSourceBanner"
import { cn } from "@/lib/utils"
import { Dna, Menu, X } from "lucide-react"

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/library", label: "Library" },
  { href: "/builder", label: "Construct Builder" },
]

export function Layout({ children }: { children: React.ReactNode }) {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-surface">
      {/* Navbar */}
      <header
        className={cn(
          "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
          scrolled
            ? "bg-white/90 backdrop-blur-lg border-b border-gray-200 shadow-sm"
            : "bg-transparent"
        )}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-lg gradient-accent flex items-center justify-center shadow-md group-hover:shadow-lg transition-shadow">
                <Dna className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-bold text-primary-900 tracking-tight">
                Pepticraft
              </span>
            </Link>

            {/* Desktop Nav */}
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  to={link.href}
                  className={cn(
                    "px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                    location.pathname === link.href
                      ? "bg-primary-50 text-primary-700"
                      : "text-primary-600 hover:text-primary-800 hover:bg-surface-alt"
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center gap-3">
              <Link to="/builder">
                <Button variant="gradient" size="sm">
                  Start Building
                </Button>
              </Link>
            </div>

            {/* Mobile menu button */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden p-2 rounded-lg text-primary-600 hover:bg-surface-alt transition-colors"
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        {mobileOpen && (
          <div className="md:hidden border-t border-gray-200 bg-white">
            <div className="px-4 py-3 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  to={link.href}
                  className={cn(
                    "block px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                    location.pathname === link.href
                      ? "bg-primary-50 text-primary-700"
                      : "text-primary-600 hover:bg-surface-alt"
                  )}
                >
                  {link.label}
                </Link>
              ))}
              <Link to="/builder" className="block pt-2">
                <Button variant="gradient" className="w-full">
                  Start Building
                </Button>
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* Which database answered. Sits below the fixed navbar and inside the page's top
          padding, so an offline banner pushes the content down rather than covering it. */}
      <div className="pt-16">
        <DataSourceBanner />
      </div>

      {/* Main Content */}
      <main>{children}</main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-surface-alt">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Dna className="w-4 h-4 text-primary-400" />
              <span className="text-sm text-gray-500">
                DKU iGEM 2026 — Pepticraft: Design Your Multifunctional Proteins for Medical Aesthetics
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <span>Pipeline 4 · Silk-Fusion Peptide Screening</span>
              <span className="hidden sm:inline">·</span>
              <span className="hidden sm:inline">v0.1.0 Preview</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
