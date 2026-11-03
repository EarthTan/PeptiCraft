import { useState, useEffect, useSyncExternalStore } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { BuildHistoryPanel } from "@/components/build-history"
import { DataSourceBanner } from "@/components/DataSourceBanner"
import {
  closeHistoryPanel,
  historyPanelOpen,
  historyPanelOpenOnServer,
  openHistoryPanel,
  subscribeHistoryPanel,
} from "@/lib/historyPanel"
import { listBuildRecords, type BuildRecord } from "@/lib/buildRecords"
import { cn } from "@/lib/utils"
import { Dna, History, Menu, X } from "lucide-react"

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/library", label: "Library" },
  { href: "/builder", label: "Construct Builder" },
]

function isCurrentPage(pathname: string, href: string) {
  if (pathname === href) return true
  return href === "/library" && (pathname.startsWith("/library/") || pathname.startsWith("/results/"))
}

export function Layout({ children }: { children: React.ReactNode }) {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  // The history panel is mounted once, here, because it is asked for from the top bar and
  // from inside the Builder. The records are read when it opens rather than kept in sync:
  // a record is written by a page, and the only moment the list has to be right is the
  // moment somebody looks at it.
  const historyOpen = useSyncExternalStore(
    subscribeHistoryPanel,
    historyPanelOpen,
    historyPanelOpenOnServer,
  )
  const [records, setRecords] = useState<BuildRecord[]>([])

  useEffect(() => {
    if (historyOpen) setRecords(listBuildRecords())
  }, [historyOpen])

  /**
   * Reopen a recorded build.
   *
   * Loading one is a navigation rather than a call into the Builder, because the panel can
   * be opened from any page: the Builder is sent the record's id and puts it back together
   * itself, which is the same path whether the reader was already there or not.
   */
  const loadRecord = (record: BuildRecord) => {
    closeHistoryPanel()
    navigate(`/builder?record=${encodeURIComponent(record.id)}`)
  }

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
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
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
            <Link to="/" aria-label="PeptiCraft home" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-lg gradient-accent flex items-center justify-center shadow-md group-hover:shadow-lg transition-shadow">
                <Dna className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-bold text-primary-900 tracking-tight">
                PeptiCraft
              </span>
            </Link>

            {/* Desktop Nav */}
            <nav aria-label="Primary navigation" className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  to={link.href}
                  aria-current={isCurrentPage(location.pathname, link.href) ? "page" : undefined}
                  className={cn(
                    "px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                    isCurrentPage(location.pathname, link.href)
                      ? "bg-primary-50 text-primary-700"
                      : "text-primary-600 hover:text-primary-800 hover:bg-surface-alt"
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={openHistoryPanel}
                className="w-8 px-0"
                aria-label="Build history"
                title="Build history"
              >
                <History className="w-4 h-4" />
              </Button>
              <Link to="/builder?new=1">
                <Button variant="gradient" size="sm">
                  Start Building
                </Button>
              </Link>
            </div>

            {/* Mobile menu button */}
            <button
              type="button"
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden p-2 rounded-lg text-primary-600 hover:bg-surface-alt transition-colors"
              aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        <nav
          id="mobile-navigation"
          aria-label="Mobile navigation"
          className={cn("md:hidden border-t border-gray-200 bg-white", !mobileOpen && "hidden")}
        >
          <div className="px-4 py-3 space-y-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                to={link.href}
                aria-current={isCurrentPage(location.pathname, link.href) ? "page" : undefined}
                className={cn(
                  "block px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isCurrentPage(location.pathname, link.href)
                    ? "bg-primary-50 text-primary-700"
                    : "text-primary-600 hover:bg-surface-alt"
                )}
              >
                {link.label}
              </Link>
            ))}
            <div className="flex items-center gap-2 pt-2">
              <Button
                variant="outline"
                onClick={openHistoryPanel}
                className="h-10 w-10 px-0"
                aria-label="Build history"
                title="Build history"
              >
                <History className="w-4 h-4" />
              </Button>
              <Link to="/builder?new=1" className="flex-1">
                <Button variant="gradient" className="w-full">
                  Start Building
                </Button>
              </Link>
            </div>
          </div>
        </nav>
      </header>

      {/* Which database answered. Sits below the fixed navbar and inside the page's top
          padding, so an offline banner pushes the content down rather than covering it. */}
      <div className="pt-16">
        <DataSourceBanner />
      </div>

      {/* Main Content */}
      <main id="main-content" tabIndex={-1}>
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-surface-alt">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Dna className="w-4 h-4 text-primary-400" />
              <span className="text-sm text-gray-500">
                DKU iGEM 2026 · PeptiCraft
              </span>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm text-gray-500">
              <span>Evidence-aware fusion-protein candidate design</span>
              <a
                href="https://2026.igem.wiki/dku/"
                target="_blank"
                rel="noreferrer"
                className="font-medium text-primary-700 underline underline-offset-4 hover:text-primary-900"
              >
                Team Wiki
              </a>
            </div>
          </div>
        </div>
      </footer>

      <BuildHistoryPanel
        open={historyOpen}
        onClose={closeHistoryPanel}
        records={records}
        onRecordsChange={setRecords}
        onLoad={loadRecord}
      />
    </div>
  )
}
