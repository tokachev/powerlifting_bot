import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type Theme = 'dark' | 'light'
export type Variant = 'industrial' | 'electric' | 'blueprint'
export type Density = 'compact' | 'comfortable' | 'roomy'

type Ctx = {
  theme: Theme
  variant: Variant
  density: Density
  setTheme: (t: Theme) => void
  setVariant: (v: Variant) => void
  setDensity: (d: Density) => void
}

const KEY_THEME = 'pwrbot.theme'
const KEY_VARIANT = 'pwrbot.variant'
const KEY_DENSITY = 'pwrbot.density'

function readStore<T extends string>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  const v = window.localStorage.getItem(key)
  return (v as T) || fallback
}

const ThemeCtx = createContext<Ctx | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readStore<Theme>(KEY_THEME, 'dark'))
  const [variant, setVariantState] = useState<Variant>(() =>
    readStore<Variant>(KEY_VARIANT, 'industrial'),
  )
  const [density, setDensityState] = useState<Density>(() =>
    readStore<Density>(KEY_DENSITY, 'comfortable'),
  )

  useEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme
    root.dataset.variant = variant
    root.dataset.density = density === 'comfortable' ? '' : density
  }, [theme, variant, density])

  const setTheme = (t: Theme) => {
    setThemeState(t)
    window.localStorage.setItem(KEY_THEME, t)
  }
  const setVariant = (v: Variant) => {
    setVariantState(v)
    window.localStorage.setItem(KEY_VARIANT, v)
  }
  const setDensity = (d: Density) => {
    setDensityState(d)
    window.localStorage.setItem(KEY_DENSITY, d)
  }

  return (
    <ThemeCtx.Provider value={{ theme, variant, density, setTheme, setVariant, setDensity }}>
      {children}
    </ThemeCtx.Provider>
  )
}

export function useTheme(): Ctx {
  const ctx = useContext(ThemeCtx)
  if (!ctx) throw new Error('useTheme outside ThemeProvider')
  return ctx
}
