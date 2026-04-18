import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import ru from './ru.json'

const LANG_KEY = 'pwrbot.lang'

const stored = (typeof window !== 'undefined' && window.localStorage.getItem(LANG_KEY)) || 'ru'

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
  },
  lng: stored,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export function setLanguage(lang: 'en' | 'ru'): void {
  i18n.changeLanguage(lang)
  if (typeof window !== 'undefined') window.localStorage.setItem(LANG_KEY, lang)
}

export { i18n }
export default i18n
