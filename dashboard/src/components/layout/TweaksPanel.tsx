import { useTranslation } from 'react-i18next'
import { setLanguage } from '@/i18n'
import { useTheme, type Theme, type Variant, type Density } from '@/theme/ThemeProvider'

interface Props {
  open: boolean
  onClose: () => void
}

export function TweaksPanel({ open, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const { theme, variant, density, setTheme, setVariant, setDensity } = useTheme()

  const themes: Theme[] = ['dark', 'light']
  const variants: Variant[] = ['industrial', 'electric', 'blueprint']
  const densities: Density[] = ['compact', 'comfortable', 'roomy']
  const langs: Array<'en' | 'ru'> = ['ru', 'en']

  const swatch = (v: Variant) => {
    if (v === 'industrial') return '#e94f2e'
    if (v === 'electric') return '#a3ff12'
    return '#4a90ff'
  }

  return (
    <div className={`tweaks-panel${open ? ' open' : ''}`}>
      <h4>
        {t('tweaks')}
        <button className="btn ghost" onClick={onClose} style={{ padding: 2 }}>
          ✕
        </button>
      </h4>

      <div className="tweak-row">
        <label>{t('theme')}</label>
        <div className="tweak-opts">
          {themes.map((th) => (
            <button key={th} className={th === theme ? 'on' : ''} onClick={() => setTheme(th)}>
              {t(th)}
            </button>
          ))}
        </div>
      </div>

      <div className="tweak-row">
        <label>{t('variant')}</label>
        <div className="tweak-swatches">
          {variants.map((v) => (
            <button
              key={v}
              className={v === variant ? 'on' : ''}
              style={{ background: swatch(v) }}
              onClick={() => setVariant(v)}
              aria-label={v}
            />
          ))}
        </div>
      </div>

      <div className="tweak-row">
        <label>{t('language')}</label>
        <div className="tweak-opts">
          {langs.map((lng) => (
            <button
              key={lng}
              className={i18n.language === lng ? 'on' : ''}
              onClick={() => setLanguage(lng)}
            >
              {lng.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="tweak-row">
        <label>{t('density')}</label>
        <div className="tweak-opts">
          {densities.map((d) => (
            <button key={d} className={d === density ? 'on' : ''} onClick={() => setDensity(d)}>
              {t(d)}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
